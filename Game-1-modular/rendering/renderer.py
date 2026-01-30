"""Renderer class - handles all game rendering including world, UI, and effects"""
from __future__ import annotations

import pygame
import os
import time
from typing import Dict, List, Optional, Tuple, Any

# Core systems
from core import Config, Camera, Notification

# Data models
from data.models import (
    Recipe, PlacementData,
    EquipmentItem,
    NPCDefinition,
    Position,
)

# Data databases
from data.databases import (
    MaterialDatabase,
    PlacementDatabase,
    EquipmentDatabase,
    RecipeDatabase,
    SkillDatabase,
    TitleDatabase,
    ClassDatabase,
    NPCDatabase,
)

# Image cache
from rendering.image_cache import ImageCache

# Entities
from entities import Character, Tool, DamageNumber
from entities.components import ItemStack

# Systems
from systems import (
    WorldSystem,
    NPC,
)

# Map/Waypoint config
from data.databases.map_waypoint_db import MapWaypointConfig


class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        # Scaled fonts for responsive UI
        self.font = pygame.font.Font(None, Config.scale(24))
        self.small_font = pygame.font.Font(None, Config.scale(18))
        self.tiny_font = pygame.font.Font(None, Config.scale(14))
        # Pending tooltip for deferred rendering (ensures tooltips render on top of all UI)
        self.pending_tooltip = None  # Tuple of (item_stack, mouse_pos, character, is_equipment)
        self.pending_class_tooltip = None  # Tuple of (class_definition, mouse_pos)
        self.pending_tool_tooltip = None  # Tuple of (tool, tool_type, mouse_pos, character)

    def _get_grid_size_for_tier(self, tier: int, discipline: str) -> Tuple[int, int]:
        """Get grid dimensions based on station tier for grid-based disciplines (smithing, adornments)"""
        if discipline not in ['smithing', 'adornments']:
            return (3, 3)  # Default for non-grid disciplines

        tier_to_grid = {
            1: (3, 3),
            2: (5, 5),
            3: (7, 7),
            4: (9, 9)
        }
        return tier_to_grid.get(tier, (3, 3))

    def _draw_material_icon(self, surf: pygame.Surface, mat, mat_id: str,
                           center_x: int, center_y: int, icon_size: int,
                           text_color: Tuple[int, int, int], dimmed: bool = False):
        """
        Helper to draw material icon or fallback to text.

        Args:
            surf: Surface to draw on
            mat: MaterialDefinition or None
            mat_id: Material ID for fallback text
            center_x, center_y: Center position for the icon
            icon_size: Size of the icon
            text_color: Color for fallback text
            dimmed: If True, apply 50% alpha for recipe hints
        """
        if mat and mat.icon_path:
            image_cache = ImageCache.get_instance()
            icon = image_cache.get_image(mat.icon_path, (icon_size, icon_size))
            if icon:
                if dimmed:
                    icon = icon.copy()
                    icon.set_alpha(128)
                icon_rect = icon.get_rect(center=(center_x, center_y))
                surf.blit(icon, icon_rect)
                return

        # Fallback to text
        mat_name = (mat.name[:8] if mat else mat_id[:8])
        text_surf = self.tiny_font.render(mat_name, True, text_color)
        text_rect = text_surf.get_rect(center=(center_x, center_y))
        surf.blit(text_surf, text_rect)

    def render_smithing_grid(self, surf: pygame.Surface, placement_rect: pygame.Rect,
                           station_tier: int, selected_recipe: Optional[Recipe],
                           user_placement: Dict[str, str], mouse_pos: Tuple[int, int]):
        """
        Render smithing grid with:
        - Station tier determines grid size shown (T1=3x3, T2=5x5, T3=7x7, T4=9x9)
        - Recipe placement data shown (if selected)
        - User's current placement overlaid
        - Visual feedback for valid/invalid placements

        Returns: Dict mapping grid cell rects to (grid_x, grid_y) for click handling
        """
        mat_db = MaterialDatabase.get_instance()
        placement_db = PlacementDatabase.get_instance()

        # Determine grid size based on station tier
        grid_w, grid_h = self._get_grid_size_for_tier(station_tier, 'smithing')

        # Calculate cell size to fit in placement_rect with padding
        padding = 20
        available_w = placement_rect.width - 2 * padding
        available_h = placement_rect.height - 2 * padding
        cell_size = min(available_w // grid_w, available_h // grid_h) - 4  # -4 for cell spacing

        # Center the grid in the placement_rect
        grid_pixel_w = grid_w * (cell_size + 4)
        grid_pixel_h = grid_h * (cell_size + 4)
        grid_start_x = placement_rect.x + (placement_rect.width - grid_pixel_w) // 2
        grid_start_y = placement_rect.y + (placement_rect.height - grid_pixel_h) // 2

        # Get recipe placement data if available
        recipe_placement_map = {}
        recipe_grid_w, recipe_grid_h = grid_w, grid_h  # Default to station grid size
        if selected_recipe:
            placement_data = placement_db.get_placement(selected_recipe.recipe_id)
            if placement_data and placement_data.grid_size:
                # Parse recipe's actual grid size (e.g., "3x3")
                parts = placement_data.grid_size.lower().split('x')
                if len(parts) == 2:
                    try:
                        recipe_grid_w = int(parts[0])
                        recipe_grid_h = int(parts[1])
                    except ValueError:
                        pass
                recipe_placement_map = placement_data.placement_map

        # Calculate offset to center recipe on station grid
        offset_x = (grid_w - recipe_grid_w) // 2
        offset_y = (grid_h - recipe_grid_h) // 2

        # Draw grid cells
        cell_rects = []  # Will store list of (pygame.Rect, (grid_x, grid_y)) for click detection

        for gy in range(1, grid_h + 1):  # 1-indexed to match placement data (row)
            for gx in range(1, grid_w + 1):  # 1-indexed (col)
                # No Y axis flipping - row 1 is at top, like in crafting_tester.py
                cell_x = grid_start_x + (gx - 1) * (cell_size + 4)
                cell_y = grid_start_y + (gy - 1) * (cell_size + 4)
                cell_rect = pygame.Rect(cell_x, cell_y, cell_size, cell_size)

                # Check if this cell corresponds to a recipe requirement (with offset for centering)
                recipe_x = gx - offset_x
                recipe_y = gy - offset_y
                # Placement data format is "row,col" where row=Y axis, col=X axis
                # gy is the row (Y), gx is the col (X), so keys should be "{row},{col}" = "{gy},{gx}"
                recipe_key = f"{recipe_y},{recipe_x}"

                grid_key = f"{gy},{gx}"
                has_recipe_requirement = (1 <= recipe_x <= recipe_grid_w and
                                        1 <= recipe_y <= recipe_grid_h and
                                        recipe_key in recipe_placement_map)
                has_user_placement = grid_key in user_placement

                # Cell background color
                if has_user_placement:
                    # User placed something here
                    cell_color = (50, 70, 50)  # Green tint
                elif has_recipe_requirement:
                    # Recipe requires something here (but user hasn't placed it yet)
                    cell_color = (70, 60, 40)  # Gold tint - shows what's needed
                else:
                    # Empty cell
                    cell_color = (30, 30, 40)

                # Highlight cell under mouse
                is_hovered = cell_rect.collidepoint(mouse_pos)
                if is_hovered:
                    cell_color = tuple(min(255, c + 20) for c in cell_color)

                pygame.draw.rect(surf, cell_color, cell_rect)

                # Border
                border_color = (100, 100, 100) if not has_recipe_requirement else (150, 130, 80)
                pygame.draw.rect(surf, border_color, cell_rect, 1 if not is_hovered else 2)

                # Draw material icon/name
                if has_user_placement:
                    # Show user's placement
                    mat_id = user_placement[grid_key]
                    mat = mat_db.get_material(mat_id)
                    # Try to show icon first
                    if mat and mat.icon_path:
                        image_cache = ImageCache.get_instance()
                        icon_size = max(cell_size - 8, 16)  # Leave 4px padding on each side, min 16px
                        icon = image_cache.get_image(mat.icon_path, (icon_size, icon_size))
                        if icon:
                            icon_rect = icon.get_rect(center=cell_rect.center)
                            surf.blit(icon, icon_rect)
                        else:
                            # Fallback to text
                            mat_name = mat.name[:6]
                            text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
                            text_rect = text_surf.get_rect(center=cell_rect.center)
                            surf.blit(text_surf, text_rect)
                    else:
                        # Fallback to text
                        mat_name = (mat.name[:6] if mat else mat_id[:6])
                        text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
                        text_rect = text_surf.get_rect(center=cell_rect.center)
                        surf.blit(text_surf, text_rect)
                elif has_recipe_requirement:
                    # Show what recipe requires (semi-transparent hint)
                    req_mat_id = recipe_placement_map[recipe_key]
                    mat = mat_db.get_material(req_mat_id)
                    # Try to show icon first (slightly dimmed for hint)
                    if mat and mat.icon_path:
                        image_cache = ImageCache.get_instance()
                        icon_size = max(cell_size - 8, 16)
                        icon = image_cache.get_image(mat.icon_path, (icon_size, icon_size))
                        if icon:
                            # Create dimmed version for hint
                            dimmed_icon = icon.copy()
                            dimmed_icon.set_alpha(128)
                            icon_rect = dimmed_icon.get_rect(center=cell_rect.center)
                            surf.blit(dimmed_icon, icon_rect)
                        else:
                            # Fallback to text
                            mat_name = mat.name[:6]
                            text_surf = self.tiny_font.render(mat_name, True, (180, 160, 120))
                            text_rect = text_surf.get_rect(center=cell_rect.center)
                            surf.blit(text_surf, text_rect)
                    else:
                        # Fallback to text
                        mat_name = (mat.name[:6] if mat else req_mat_id[:6])
                        text_surf = self.tiny_font.render(mat_name, True, (180, 160, 120))
                        text_rect = text_surf.get_rect(center=cell_rect.center)
                        surf.blit(text_surf, text_rect)

                # Store rect for click handling
                cell_rects.append((cell_rect, (gx, gy)))

        # Draw grid size label
        grid_label = f"Smithing Grid: {grid_w}x{grid_h} (T{station_tier})"
        label_surf = self.small_font.render(grid_label, True, (150, 150, 150))
        surf.blit(label_surf, (placement_rect.x + 10, placement_rect.y + 5))

        return cell_rects

    def render_adornment_pattern(self, surf: pygame.Surface, placement_rect: pygame.Rect,
                                 station_tier: int, selected_recipe: Optional[Recipe],
                                 user_placement: Dict[str, str], mouse_pos: Tuple[int, int]):
        """
        Render adornment/enchanting pattern grid with vertices and shapes:
        - Uses centered coordinate system (0,0 at center)
        - Shows vertices as circles with material labels
        - Draws connecting lines for shapes
        - Supports different grid sizes (8x8, 10x10, 12x12, etc.)

        Returns: List of (pygame.Rect, vertex_coord_str) for click handling
        """
        mat_db = MaterialDatabase.get_instance()
        placement_db = PlacementDatabase.get_instance()

        # Get placement data for selected recipe
        vertices = {}
        shapes = []
        grid_size = 12  # Default grid size

        if selected_recipe:
            placement_data = placement_db.get_placement(selected_recipe.recipe_id)
            if placement_data and placement_data.placement_map:
                pmap = placement_data.placement_map
                vertices = pmap.get('vertices', {})
                shapes = pmap.get('shapes', [])
                # Parse grid type (e.g., "square_12x12")
                grid_type = pmap.get('gridType', 'square_12x12')
                if 'x' in grid_type:
                    try:
                        grid_size = int(grid_type.split('_')[1].split('x')[0])
                    except (IndexError, ValueError):
                        pass

        # Calculate cell size to fit grid in placement_rect
        padding = 40
        available = min(placement_rect.width, placement_rect.height) - 2 * padding
        cell_size = available // grid_size

        # Center the grid
        grid_pixel_size = grid_size * cell_size
        grid_start_x = placement_rect.x + (placement_rect.width - grid_pixel_size) // 2
        grid_start_y = placement_rect.y + (placement_rect.height - grid_pixel_size) // 2

        # Draw grid background
        grid_rect = pygame.Rect(grid_start_x, grid_start_y, grid_pixel_size, grid_pixel_size)
        pygame.draw.rect(surf, (25, 25, 35), grid_rect)

        # Draw grid cells
        for row in range(grid_size):
            for col in range(grid_size):
                x = grid_start_x + col * cell_size
                y = grid_start_y + row * cell_size
                cell_rect = pygame.Rect(x, y, cell_size - 1, cell_size - 1)
                pygame.draw.rect(surf, (40, 40, 50), cell_rect, 1)

        # Draw center axes
        half = grid_size // 2
        center_x = grid_start_x + half * cell_size
        center_y = grid_start_y + half * cell_size
        pygame.draw.line(surf, (60, 60, 70), (center_x, grid_start_y), (center_x, grid_start_y + grid_pixel_size), 2)
        pygame.draw.line(surf, (60, 60, 70), (grid_start_x, center_y), (grid_start_x + grid_pixel_size, center_y), 2)

        # Draw shape connecting lines first (behind vertices)
        for shape in shapes:
            shape_vertices = shape.get('vertices', [])
            if len(shape_vertices) > 1:
                for i in range(len(shape_vertices)):
                    v1_str = shape_vertices[i]
                    v2_str = shape_vertices[(i + 1) % len(shape_vertices)]

                    if ',' in v1_str and ',' in v2_str:
                        try:
                            gx1, gy1 = map(int, v1_str.split(','))
                            gx2, gy2 = map(int, v2_str.split(','))

                            # Convert centered coords to screen position
                            sx1 = grid_start_x + (gx1 + half) * cell_size + cell_size // 2
                            sy1 = grid_start_y + (half - gy1) * cell_size + cell_size // 2
                            sx2 = grid_start_x + (gx2 + half) * cell_size + cell_size // 2
                            sy2 = grid_start_y + (half - gy2) * cell_size + cell_size // 2

                            pygame.draw.line(surf, (100, 150, 255), (sx1, sy1), (sx2, sy2), 3)
                        except (ValueError, IndexError):
                            pass

        # Draw vertices (material placement points)
        vertex_rects = []
        for coord_str, vertex_data in vertices.items():
            if ',' in coord_str:
                try:
                    gx, gy = map(int, coord_str.split(','))

                    # Convert centered coordinates to screen position
                    screen_x = grid_start_x + (gx + half) * cell_size + cell_size // 2
                    screen_y = grid_start_y + (half - gy) * cell_size + cell_size // 2

                    material_id = vertex_data.get('materialId')
                    is_key = vertex_data.get('isKey', False)

                    # Determine color
                    if material_id:
                        mat = mat_db.get_material(material_id)
                        if mat:
                            mat_color = Config.RARITY_COLORS.get(mat.rarity, (100, 200, 200))
                        else:
                            mat_color = (255, 100, 100) if is_key else (100, 200, 200)
                    else:
                        mat_color = (255, 100, 100) if is_key else (100, 200, 200)

                    # Draw larger, more visible circle
                    pygame.draw.circle(surf, mat_color, (screen_x, screen_y), 10)
                    pygame.draw.circle(surf, (255, 255, 255), (screen_x, screen_y), 10, 2)

                    # Draw inner dot for key vertices
                    if is_key:
                        pygame.draw.circle(surf, (255, 255, 0), (screen_x, screen_y), 4)

                    # Draw material label with shadow for visibility
                    if material_id:
                        mat_label = material_id[:4].upper()
                        # Shadow
                        label_shadow = self.tiny_font.render(mat_label, True, (0, 0, 0))
                        surf.blit(label_shadow, (screen_x - 10, screen_y - 22))
                        surf.blit(label_shadow, (screen_x - 8, screen_y - 20))
                        # Main text
                        label_text = self.tiny_font.render(mat_label, True, (255, 255, 255))
                        surf.blit(label_text, (screen_x - 9, screen_y - 21))

                    # Store for click handling
                    vertex_rect = pygame.Rect(screen_x - 10, screen_y - 10, 20, 20)
                    vertex_rects.append((vertex_rect, coord_str))

                except (ValueError, IndexError):
                    pass

        # Draw grid label
        grid_label = f"Adornment Pattern: {grid_size}x{grid_size} ({len(vertices)} vertices)"
        label_surf = self.small_font.render(grid_label, True, (150, 150, 200))
        surf.blit(label_surf, (placement_rect.x + 10, placement_rect.y + 5))

        return vertex_rects

    def render_refining_hub(self, surf: pygame.Surface, placement_rect: pygame.Rect,
                          station_tier: int, selected_recipe: Optional[Recipe],
                          user_placement: Dict[str, str], mouse_pos: Tuple[int, int]):
        """
        Render refining hub-and-spoke with:
        - Station tier determines number of slots
        - Core slots in center (hub) - T1/T2=1, T3=2, T4=3
        - Surrounding slots in circle around core (spokes)
        - User can place materials in slots

        Returns: Dict mapping slot rects to slot_id for click handling
        """
        mat_db = MaterialDatabase.get_instance()
        placement_db = PlacementDatabase.get_instance()

        # Determine slot counts based on station tier - MUST MATCH interactive_crafting.py
        slot_config = {
            1: {'core': 1, 'surrounding': 2},
            2: {'core': 1, 'surrounding': 4},
            3: {'core': 2, 'surrounding': 5},
            4: {'core': 3, 'surrounding': 6}
        }
        config = slot_config.get(station_tier, {'core': 1, 'surrounding': 2})
        num_core_slots = config['core']
        num_surrounding_slots = config['surrounding']

        # Get recipe placement data if available
        required_core = []
        required_surrounding = []
        if selected_recipe:
            placement_data = placement_db.get_placement(selected_recipe.recipe_id)
            if placement_data:
                required_core = placement_data.core_inputs
                required_surrounding = placement_data.surrounding_inputs

        # Calculate slot size
        center_x = placement_rect.centerx
        center_y = placement_rect.centery
        core_radius = 35  # Radius of core slot (slightly smaller for multiple)
        surrounding_radius = 30  # Radius of each surrounding slot
        orbit_radius = 100  # Distance from center to surrounding slots

        slot_rects = []  # Will store list of (pygame.Rect, slot_id) for click detection

        # Calculate core slot positions based on number of cores
        # 1 core: center, 2 cores: horizontal, 3 cores: triangle
        core_positions = []
        if num_core_slots == 1:
            core_positions = [(center_x, center_y)]
        elif num_core_slots == 2:
            spacing = core_radius * 2 + 10
            core_positions = [
                (center_x - spacing // 2, center_y),
                (center_x + spacing // 2, center_y)
            ]
        elif num_core_slots == 3:
            spacing = core_radius * 2 + 5
            core_positions = [
                (center_x, center_y - spacing // 2),  # Top
                (center_x - spacing // 2, center_y + spacing // 3),  # Bottom left
                (center_x + spacing // 2, center_y + spacing // 3)   # Bottom right
            ]

        # Draw all core slots
        for core_idx, (core_cx, core_cy) in enumerate(core_positions):
            core_rect = pygame.Rect(
                core_cx - core_radius,
                core_cy - core_radius,
                core_radius * 2,
                core_radius * 2
            )

            slot_id = f"core_{core_idx}"
            has_user_core = slot_id in user_placement
            has_required_core = core_idx < len(required_core)

            core_color = (50, 70, 50) if has_user_core else ((70, 60, 40) if has_required_core else (30, 30, 40))
            is_hovered = core_rect.collidepoint(mouse_pos)
            if is_hovered:
                core_color = tuple(min(255, c + 20) for c in core_color)

            pygame.draw.circle(surf, core_color, (core_cx, core_cy), core_radius)
            pygame.draw.circle(surf, (150, 130, 80), (core_cx, core_cy), core_radius, 2 if is_hovered else 1)

            # Draw core material
            if has_user_core:
                mat_id = user_placement[slot_id]
                mat = mat_db.get_material(mat_id)
                self._draw_material_icon(surf, mat, mat_id, core_cx, core_cy, core_radius * 2 - 16, (200, 255, 200))
            elif has_required_core:
                req_mat_id = required_core[core_idx].get('materialId', '')
                mat = mat_db.get_material(req_mat_id)
                self._draw_material_icon(surf, mat, req_mat_id, core_cx, core_cy, core_radius * 2 - 16, (180, 160, 120), dimmed=True)

            slot_rects.append((core_rect, slot_id))

        # Draw surrounding slots in circle
        import math
        for i in range(num_surrounding_slots):
            angle = (2 * math.pi * i) / num_surrounding_slots - math.pi / 2  # Start at top
            slot_x = center_x + int(orbit_radius * math.cos(angle))
            slot_y = center_y + int(orbit_radius * math.sin(angle))

            slot_rect = pygame.Rect(
                slot_x - surrounding_radius,
                slot_y - surrounding_radius,
                surrounding_radius * 2,
                surrounding_radius * 2
            )

            slot_id = f"surrounding_{i}"
            has_user_surrounding = slot_id in user_placement
            has_required_surrounding = i < len(required_surrounding)

            slot_color = (50, 70, 50) if has_user_surrounding else ((70, 60, 40) if has_required_surrounding else (30, 30, 40))
            is_hovered = slot_rect.collidepoint(mouse_pos)
            if is_hovered:
                slot_color = tuple(min(255, c + 20) for c in slot_color)

            pygame.draw.circle(surf, slot_color, (slot_x, slot_y), surrounding_radius)
            pygame.draw.circle(surf, (100, 100, 100), (slot_x, slot_y), surrounding_radius, 2 if is_hovered else 1)

            # Draw slot material
            if has_user_surrounding:
                mat_id = user_placement[slot_id]
                mat = mat_db.get_material(mat_id)
                # Try to show icon first
                if mat and mat.icon_path:
                    image_cache = ImageCache.get_instance()
                    icon_size = surrounding_radius * 2 - 12  # Leave some padding
                    icon = image_cache.get_image(mat.icon_path, (icon_size, icon_size))
                    if icon:
                        icon_rect = icon.get_rect(center=(slot_x, slot_y))
                        surf.blit(icon, icon_rect)
                    else:
                        # Fallback to text
                        mat_name = mat.name[:6]
                        text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
                        text_rect = text_surf.get_rect(center=(slot_x, slot_y))
                        surf.blit(text_surf, text_rect)
                else:
                    # Fallback to text
                    mat_name = (mat.name[:6] if mat else mat_id[:6])
                    text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
                    text_rect = text_surf.get_rect(center=(slot_x, slot_y))
                    surf.blit(text_surf, text_rect)
            elif has_required_surrounding:
                req_mat_id = required_surrounding[i].get('materialId', '')
                mat = mat_db.get_material(req_mat_id)
                # Try to show icon first (dimmed for hint)
                if mat and mat.icon_path:
                    image_cache = ImageCache.get_instance()
                    icon_size = surrounding_radius * 2 - 12
                    icon = image_cache.get_image(mat.icon_path, (icon_size, icon_size))
                    if icon:
                        dimmed_icon = icon.copy()
                        dimmed_icon.set_alpha(128)
                        icon_rect = dimmed_icon.get_rect(center=(slot_x, slot_y))
                        surf.blit(dimmed_icon, icon_rect)
                    else:
                        # Fallback to text
                        mat_name = mat.name[:6]
                        text_surf = self.tiny_font.render(mat_name, True, (180, 160, 120))
                        text_rect = text_surf.get_rect(center=(slot_x, slot_y))
                        surf.blit(text_surf, text_rect)
                else:
                    # Fallback to text
                    mat_name = (mat.name[:6] if mat else req_mat_id[:6])
                    text_surf = self.tiny_font.render(mat_name, True, (180, 160, 120))
                    text_rect = text_surf.get_rect(center=(slot_x, slot_y))
                    surf.blit(text_surf, text_rect)

            slot_rects.append((slot_rect, slot_id))

        # Draw label
        label = f"Refining Hub: {num_core_slots} core + {num_surrounding_slots} surrounding (T{station_tier})"
        label_surf = self.small_font.render(label, True, (150, 150, 150))
        surf.blit(label_surf, (placement_rect.x + 10, placement_rect.y + 5))

        return slot_rects

    def render_alchemy_sequence(self, surf: pygame.Surface, placement_rect: pygame.Rect,
                               station_tier: int, selected_recipe: Optional[Recipe],
                               user_placement: Dict[str, str], mouse_pos: Tuple[int, int]):
        """
        Render alchemy sequential placement with:
        - Station tier determines max slots (T1=2, T2=3, T3=4, T4=5)
        - Horizontal sequence of numbered slots
        - Order is critical for alchemy reactions

        Returns: List of (pygame.Rect, slot_id) for click handling
        """
        mat_db = MaterialDatabase.get_instance()
        placement_db = PlacementDatabase.get_instance()

        # Determine max slots based on station tier
        max_slots = 1 + station_tier  # T1=2, T2=3, T3=4, T4=5

        # Get recipe placement data if available
        required_ingredients = []
        if selected_recipe:
            placement_data = placement_db.get_placement(selected_recipe.recipe_id)
            if placement_data:
                required_ingredients = placement_data.ingredients

        # Calculate slot dimensions
        slot_width = 80
        slot_height = 80
        slot_spacing = 20
        total_width = max_slots * slot_width + (max_slots - 1) * slot_spacing

        start_x = placement_rect.centerx - total_width // 2
        start_y = placement_rect.centery - slot_height // 2

        slot_rects = []  # Will store list of (pygame.Rect, slot_id) for click detection

        # Draw slots horizontally
        for i in range(max_slots):
            slot_num = i + 1  # 1-indexed
            slot_x = start_x + i * (slot_width + slot_spacing)
            slot_y = start_y

            slot_rect = pygame.Rect(slot_x, slot_y, slot_width, slot_height)
            slot_id = f"seq_{slot_num}"

            # Find if this slot is required
            required_for_slot = None
            for ing in required_ingredients:
                if ing.get('slot') == slot_num:
                    required_for_slot = ing
                    break

            has_user_material = slot_id in user_placement
            has_requirement = required_for_slot is not None

            # Slot background color
            slot_color = (50, 70, 50) if has_user_material else ((70, 60, 40) if has_requirement else (30, 30, 40))
            is_hovered = slot_rect.collidepoint(mouse_pos)
            if is_hovered:
                slot_color = tuple(min(255, c + 20) for c in slot_color)

            pygame.draw.rect(surf, slot_color, slot_rect)
            pygame.draw.rect(surf, (100, 100, 100), slot_rect, 2 if is_hovered else 1)

            # Draw slot number
            num_surf = self.font.render(str(slot_num), True, (150, 150, 150))
            num_rect = num_surf.get_rect(topleft=(slot_x + 5, slot_y + 5))
            surf.blit(num_surf, num_rect)

            # Draw material icon/name
            if has_user_material:
                mat_id = user_placement[slot_id]
                mat = mat_db.get_material(mat_id)
                # Try to show icon first
                if mat and mat.icon_path:
                    image_cache = ImageCache.get_instance()
                    icon_size = min(slot_width - 20, slot_height - 40)  # Leave room for slot number and name
                    icon = image_cache.get_image(mat.icon_path, (icon_size, icon_size))
                    if icon:
                        icon_rect = icon.get_rect(center=(slot_rect.centerx, slot_rect.centery + 5))
                        surf.blit(icon, icon_rect)
                        # Show small name below icon
                        name_surf = self.tiny_font.render(mat.name[:10], True, (200, 255, 200))
                        name_rect = name_surf.get_rect(center=(slot_rect.centerx, slot_rect.bottom - 8))
                        surf.blit(name_surf, name_rect)
                    else:
                        # Fallback to text only
                        mat_name = mat.name[:10]
                        text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
                        text_rect = text_surf.get_rect(center=(slot_rect.centerx, slot_rect.centery + 15))
                        surf.blit(text_surf, text_rect)
                else:
                    # Fallback to text only
                    mat_name = (mat.name[:10] if mat else mat_id[:10])
                    text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
                    text_rect = text_surf.get_rect(center=(slot_rect.centerx, slot_rect.centery + 15))
                    surf.blit(text_surf, text_rect)

                # Draw quantity if available (from requirements)
                if has_requirement:
                    qty = required_for_slot.get('quantity', 1)
                    if qty > 1:
                        qty_text = f"x{qty}"
                        qty_surf = self.tiny_font.render(qty_text, True, (255, 255, 255))
                        qty_x = slot_rect.right - qty_surf.get_width() - 5
                        qty_y = slot_rect.top + 5
                        # Draw semi-transparent black background
                        qty_bg = pygame.Rect(qty_x - 2, qty_y - 2, qty_surf.get_width() + 4, qty_surf.get_height() + 4)
                        pygame.draw.rect(surf, (0, 0, 0, 180), qty_bg)
                        surf.blit(qty_surf, (qty_x, qty_y))
            elif has_requirement:
                req_mat_id = required_for_slot.get('materialId', '')
                mat = mat_db.get_material(req_mat_id)
                # Try to show icon first (dimmed for hint)
                if mat and mat.icon_path:
                    image_cache = ImageCache.get_instance()
                    icon_size = min(slot_width - 20, slot_height - 40)
                    icon = image_cache.get_image(mat.icon_path, (icon_size, icon_size))
                    if icon:
                        dimmed_icon = icon.copy()
                        dimmed_icon.set_alpha(128)
                        icon_rect = dimmed_icon.get_rect(center=(slot_rect.centerx, slot_rect.centery + 5))
                        surf.blit(dimmed_icon, icon_rect)
                        # Show small name below icon
                        name_surf = self.tiny_font.render(mat.name[:10], True, (180, 160, 120))
                        name_rect = name_surf.get_rect(center=(slot_rect.centerx, slot_rect.bottom - 8))
                        surf.blit(name_surf, name_rect)
                    else:
                        # Fallback to text only
                        mat_name = mat.name[:10]
                        text_surf = self.tiny_font.render(mat_name, True, (180, 160, 120))
                        text_rect = text_surf.get_rect(center=(slot_rect.centerx, slot_rect.centery + 15))
                        surf.blit(text_surf, text_rect)
                else:
                    # Fallback to text only
                    mat_name = (mat.name[:10] if mat else req_mat_id[:10])
                    text_surf = self.tiny_font.render(mat_name, True, (180, 160, 120))
                    text_rect = text_surf.get_rect(center=(slot_rect.centerx, slot_rect.centery + 15))
                    surf.blit(text_surf, text_rect)

                # Draw quantity (dimmed hint)
                qty = required_for_slot.get('quantity', 1)
                if qty > 1:
                    qty_text = f"x{qty}"
                    qty_surf = self.tiny_font.render(qty_text, True, (200, 200, 200))
                    qty_x = slot_rect.right - qty_surf.get_width() - 5
                    qty_y = slot_rect.top + 5
                    # Draw semi-transparent black background
                    qty_bg = pygame.Rect(qty_x - 2, qty_y - 2, qty_surf.get_width() + 4, qty_surf.get_height() + 4)
                    pygame.draw.rect(surf, (0, 0, 0, 128), qty_bg)
                    surf.blit(qty_surf, (qty_x, qty_y))

            slot_rects.append((slot_rect, slot_id))

            # Draw arrow between slots
            if i < max_slots - 1:
                arrow_start_x = slot_x + slot_width
                arrow_end_x = arrow_start_x + slot_spacing
                arrow_y = slot_y + slot_height // 2
                pygame.draw.line(surf, (100, 100, 100), (arrow_start_x, arrow_y), (arrow_end_x, arrow_y), 2)
                # Arrowhead
                pygame.draw.polygon(surf, (100, 100, 100), [
                    (arrow_end_x, arrow_y),
                    (arrow_end_x - 8, arrow_y - 5),
                    (arrow_end_x - 8, arrow_y + 5)
                ])

        # Draw label
        label = f"Alchemy Sequence: {max_slots} sequential slots (T{station_tier})"
        label_surf = self.small_font.render(label, True, (150, 150, 150))
        surf.blit(label_surf, (placement_rect.x + 10, placement_rect.y + 5))

        return slot_rects

    def render_engineering_slots(self, surf: pygame.Surface, placement_rect: pygame.Rect,
                                 station_tier: int, selected_recipe: Optional[Recipe],
                                 user_placement: Dict[str, str], mouse_pos: Tuple[int, int]):
        """
        Render engineering slot-type placement with:
        - Station tier determines max slots (T1=3, T2=5, T3=5, T4=7)
        - Vertical list of typed slots (FRAME, FUNCTION, POWER, MODIFIER, etc.)
        - Each slot shows its type and required material

        Returns: List of (pygame.Rect, slot_id) for click handling
        """
        mat_db = MaterialDatabase.get_instance()
        placement_db = PlacementDatabase.get_instance()

        # Determine max slots based on station tier
        tier_to_max_slots = {1: 3, 2: 5, 3: 5, 4: 7}
        max_slots = tier_to_max_slots.get(station_tier, 3)

        # Get recipe placement data if available
        required_slots = []
        if selected_recipe:
            placement_data = placement_db.get_placement(selected_recipe.recipe_id)
            if placement_data:
                required_slots = placement_data.slots

        # Calculate slot dimensions
        slot_width = 300
        slot_height = 60
        slot_spacing = 10
        total_height = min(len(required_slots), max_slots) * (slot_height + slot_spacing) if required_slots else max_slots * (slot_height + slot_spacing)

        start_x = placement_rect.centerx - slot_width // 2
        start_y = placement_rect.centery - total_height // 2

        slot_rects = []  # Will store list of (pygame.Rect, slot_id) for click handling

        # Draw slots vertically
        num_slots = max(len(required_slots), 1) if required_slots else max_slots
        for i in range(num_slots):
            slot_y = start_y + i * (slot_height + slot_spacing)
            slot_rect = pygame.Rect(start_x, slot_y, slot_width, slot_height)
            slot_id = f"eng_slot_{i}"

            # Get required slot info
            required_slot = required_slots[i] if i < len(required_slots) else None
            has_user_material = slot_id in user_placement
            has_requirement = required_slot is not None

            # Slot background color
            slot_color = (50, 70, 50) if has_user_material else ((70, 60, 40) if has_requirement else (30, 30, 40))
            is_hovered = slot_rect.collidepoint(mouse_pos)
            if is_hovered:
                slot_color = tuple(min(255, c + 20) for c in slot_color)

            pygame.draw.rect(surf, slot_color, slot_rect)
            pygame.draw.rect(surf, (100, 100, 100), slot_rect, 2 if is_hovered else 1)

            # Draw slot type label (left side)
            if has_requirement:
                slot_type = required_slot.get('type', 'UNKNOWN')
                type_color = {
                    'FRAME': (150, 150, 200),
                    'FUNCTION': (200, 150, 100),
                    'POWER': (200, 100, 100),
                    'MODIFIER': (150, 200, 150),
                    'STABILIZER': (180, 180, 100)
                }.get(slot_type, (150, 150, 150))

                type_surf = self.small_font.render(slot_type, True, type_color)
                surf.blit(type_surf, (slot_rect.x + 10, slot_rect.y + 10))

                # Draw material icon/name (right side)
                mat_id = required_slot.get('materialId', '')
                mat = mat_db.get_material(mat_id)
                mat_name = mat.name if mat else mat_id

                if has_user_material:
                    # Show user's material (green)
                    user_mat_id = user_placement[slot_id]
                    user_mat = mat_db.get_material(user_mat_id)
                    # Try to show icon first
                    if user_mat and user_mat.icon_path:
                        image_cache = ImageCache.get_instance()
                        icon_size = slot_height - 16
                        icon = image_cache.get_image(user_mat.icon_path, (icon_size, icon_size))
                        if icon:
                            surf.blit(icon, (slot_rect.x + 120, slot_rect.y + 8))
                            # Show name next to icon
                            user_mat_name = user_mat.name if user_mat else user_mat_id
                            mat_surf = self.small_font.render(user_mat_name, True, (200, 255, 200))
                            surf.blit(mat_surf, (slot_rect.x + 170, slot_rect.y + 15))
                        else:
                            # Fallback to text only
                            user_mat_name = user_mat.name if user_mat else user_mat_id
                            mat_surf = self.small_font.render(user_mat_name, True, (200, 255, 200))
                            surf.blit(mat_surf, (slot_rect.x + 120, slot_rect.y + 10))
                    else:
                        # Fallback to text only
                        user_mat_name = user_mat.name if user_mat else user_mat_id
                        mat_surf = self.small_font.render(user_mat_name, True, (200, 255, 200))
                        surf.blit(mat_surf, (slot_rect.x + 120, slot_rect.y + 10))
                else:
                    # Show required material (gold hint) with dimmed icon
                    if mat and mat.icon_path:
                        image_cache = ImageCache.get_instance()
                        icon_size = slot_height - 16
                        icon = image_cache.get_image(mat.icon_path, (icon_size, icon_size))
                        if icon:
                            dimmed_icon = icon.copy()
                            dimmed_icon.set_alpha(128)
                            surf.blit(dimmed_icon, (slot_rect.x + 120, slot_rect.y + 8))
                            # Show name next to icon
                            mat_surf = self.small_font.render(mat_name, True, (180, 160, 120))
                            surf.blit(mat_surf, (slot_rect.x + 170, slot_rect.y + 15))
                        else:
                            # Fallback to text only
                            mat_surf = self.small_font.render(mat_name, True, (180, 160, 120))
                            surf.blit(mat_surf, (slot_rect.x + 120, slot_rect.y + 10))
                    else:
                        # Fallback to text only
                        mat_surf = self.small_font.render(mat_name, True, (180, 160, 120))
                        surf.blit(mat_surf, (slot_rect.x + 120, slot_rect.y + 10))

                # Draw quantity with background for better visibility (LEFT SIDE, outside green box)
                qty = required_slot.get('quantity', 1)
                qty_text = f"x{qty}"
                qty_surf = self.font.render(qty_text, True, (255, 255, 255))
                # Position to the LEFT of the slot, outside the placement box
                qty_x = slot_rect.x - qty_surf.get_width() - 15
                qty_y = slot_rect.y + slot_height // 2 - qty_surf.get_height() // 2
                # Draw semi-transparent black background
                qty_bg = pygame.Rect(qty_x - 2, qty_y - 2, qty_surf.get_width() + 4, qty_surf.get_height() + 4)
                pygame.draw.rect(surf, (0, 0, 0, 180), qty_bg)
                surf.blit(qty_surf, (qty_x, qty_y))

            slot_rects.append((slot_rect, slot_id))

        # Draw label
        label = f"Engineering Slots: {max_slots} max slots (T{station_tier})"
        label_surf = self.small_font.render(label, True, (150, 150, 150))
        surf.blit(label_surf, (placement_rect.x + 10, placement_rect.y + 5))

        return slot_rects

    def render_npcs(self, camera: Camera, character: Character):
        """Render NPCs in the world with interaction indicators"""
        # Get NPCs from game engine (passed via temporary attribute)
        if not hasattr(self, '_temp_npcs'):
            return

        npcs = self._temp_npcs

        for npc in npcs:
            nx, ny = camera.world_to_screen(npc.position)

            # Check if NPC is visible on screen
            if not (-Config.TILE_SIZE <= nx <= Config.VIEWPORT_WIDTH + Config.TILE_SIZE and
                    -Config.TILE_SIZE <= ny <= Config.VIEWPORT_HEIGHT + Config.TILE_SIZE):
                continue

            # Check if player is in interaction range
            is_near = npc.is_near(character.position)

            # NPC body (square sprite)
            size = Config.TILE_SIZE - 4
            npc_rect = pygame.Rect(nx - size // 2, ny - size // 2, size, size)

            # Try to load NPC icon
            npc_icon_path = f"npcs/{npc.npc_def.npc_id}.png"
            image_cache = ImageCache.get_instance()
            npc_icon = image_cache.get_image(npc_icon_path, (size, size))

            if npc_icon:
                # Render icon
                self.screen.blit(npc_icon, npc_rect.topleft)
            else:
                # Fallback: Draw NPC with sprite color
                pygame.draw.rect(self.screen, npc.npc_def.sprite_color, npc_rect)

            # Border color based on proximity
            if is_near:
                border_color = (255, 255, 100)  # Yellow when in range
                border_width = 3
            else:
                border_color = (0, 0, 0)
                border_width = 2

            pygame.draw.rect(self.screen, border_color, npc_rect, border_width)

            # NPC name above sprite
            name_surf = self.tiny_font.render(npc.npc_def.name, True, (255, 255, 255))
            name_bg = pygame.Rect(nx - name_surf.get_width() // 2 - 2, ny - size // 2 - 16,
                                name_surf.get_width() + 4, name_surf.get_height() + 2)
            pygame.draw.rect(self.screen, (0, 0, 0, 180), name_bg)
            self.screen.blit(name_surf, (nx - name_surf.get_width() // 2, ny - size // 2 - 15))

            # Interaction indicator when player is nearby
            if is_near:
                indicator_text = "[F] Talk"
                indicator_surf = self.tiny_font.render(indicator_text, True, (255, 255, 100))
                indicator_bg = pygame.Rect(nx - indicator_surf.get_width() // 2 - 2, ny + size // 2 + 4,
                                         indicator_surf.get_width() + 4, indicator_surf.get_height() + 2)
                pygame.draw.rect(self.screen, (0, 0, 0, 200), indicator_bg)
                self.screen.blit(indicator_surf, (nx - indicator_surf.get_width() // 2, ny + size // 2 + 5))

    def render_world(self, world: WorldSystem, camera: Camera, character: Character,
                     damage_numbers: List[DamageNumber], combat_manager=None):
        pygame.draw.rect(self.screen, Config.COLOR_BACKGROUND, (0, 0, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT))

        for tile in world.get_visible_tiles(camera.position, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT):
            sx, sy = camera.world_to_screen(tile.position)
            if -Config.TILE_SIZE <= sx <= Config.VIEWPORT_WIDTH and -Config.TILE_SIZE <= sy <= Config.VIEWPORT_HEIGHT:
                rect = pygame.Rect(sx, sy, Config.TILE_SIZE, Config.TILE_SIZE)
                pygame.draw.rect(self.screen, tile.get_color(), rect)
                pygame.draw.rect(self.screen, Config.COLOR_GRID, rect, 1)

        for station in world.get_visible_stations(camera.position, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT):
            sx, sy = camera.world_to_screen(station.position)
            in_range = character.is_in_range(station.position)
            size = Config.TILE_SIZE + 8  # Larger than before (was - 8, now + 8)

            # Map station type to icon name
            station_icon_map = {
                'smithing': 'forge',
                'alchemy': 'alchemy_table',
                'refining': 'refinery',
                'engineering': 'engineering_bench',
                'adornments': 'enchanting_table'
            }
            station_name = station_icon_map.get(station.station_type.value, station.station_type.value)
            station_icon_path = f"stations/{station_name}_t{station.tier}.png"

            # Try to load station icon
            image_cache = ImageCache.get_instance()
            icon = image_cache.get_image(station_icon_path, (size, size))

            if icon:
                # Render icon
                icon_rect = pygame.Rect(sx - size // 2, sy - size // 2, size, size)
                self.screen.blit(icon, icon_rect.topleft)
                # Border
                border_color = (100, 200, 100) if in_range else (80, 80, 80)
                pygame.draw.rect(self.screen, border_color, icon_rect, 3)
            else:
                # Fallback: colored diamond
                color = station.get_color() if in_range else tuple(max(0, c - 50) for c in station.get_color())
                pts = [(sx, sy - size // 2), (sx + size // 2, sy), (sx, sy + size // 2), (sx - size // 2, sy)]
                pygame.draw.polygon(self.screen, color, pts)
                pygame.draw.polygon(self.screen, (0, 0, 0), pts, 3)

            if in_range:
                tier_text = f"T{station.tier}"
                tier_surf = self.small_font.render(tier_text, True, (255, 255, 255))
                tier_rect = tier_surf.get_rect(center=(sx, sy - size // 2 - 10))
                # Draw text with black outline
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    self.screen.blit(self.small_font.render(tier_text, True, (0, 0, 0)),
                                     (tier_rect.x + dx, tier_rect.y + dy))
                self.screen.blit(tier_surf, tier_rect)

        # Render placed entities (turrets, traps, crafting stations, etc.)
        from data.models import PlacedEntityType
        for entity in world.get_visible_placed_entities(camera.position, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT):
            sx, sy = camera.world_to_screen(entity.position)
            size = Config.TILE_SIZE
            rect = pygame.Rect(sx - size // 2, sy - size // 2, size, size)

            # Construct icon path based on entity type
            icon_path = None
            if entity.entity_type == PlacedEntityType.CRAFTING_STATION:
                # Crafting stations (already handled below, but we can preview here)
                # Using pattern: stations/{station_name}_t{tier}.png
                pass  # Will use existing crafting station rendering
            else:
                # Devices (turrets, traps, bombs, etc.) use: devices/{item_id}.png
                # ImageCache will try assets/devices/{item_id}.png then assets/items/devices/{item_id}.png
                icon_path = f"devices/{entity.item_id}.png"

            # Try to load and render entity icon
            image_cache = ImageCache.get_instance()
            icon = None
            if icon_path:
                icon = image_cache.get_image(icon_path, (size, size))

            if icon:
                # Render icon
                icon_rect = icon.get_rect(center=(sx, sy))
                self.screen.blit(icon, icon_rect)
            else:
                # Fallback to colored rectangle if no icon
                color = entity.get_color()
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, (0, 0, 0), rect, 2)

            # Render tier indicator
            tier_text = f"T{entity.tier}"
            tier_surf = self.tiny_font.render(tier_text, True, (255, 255, 255))
            tier_bg = pygame.Rect(sx - size // 2 + 2, sy - size // 2 + 2,
                                  tier_surf.get_width() + 4, tier_surf.get_height() + 2)
            pygame.draw.rect(self.screen, (0, 0, 0, 180), tier_bg)
            self.screen.blit(tier_surf, (sx - size // 2 + 4, sy - size // 2 + 2))

            # Render lifetime bar (only for combat entities, not crafting stations)
            if entity.entity_type != PlacedEntityType.CRAFTING_STATION:
                # Skip entities with infinite lifetime
                if hasattr(entity, 'lifetime') and entity.lifetime != float('inf'):
                    bar_w, bar_h = size - 4, 4
                    bar_y = sy + size // 2 + 4
                    pygame.draw.rect(self.screen, (100, 100, 100), (sx - bar_w // 2, bar_y, bar_w, bar_h))
                    lifetime_w = int(bar_w * (entity.time_remaining / entity.lifetime))
                    # Color based on time remaining (green -> yellow -> red)
                    if entity.time_remaining > entity.lifetime * 0.5:
                        bar_color = (0, 255, 0)  # Green
                    elif entity.time_remaining > entity.lifetime * 0.25:
                        bar_color = (255, 255, 0)  # Yellow
                    else:
                        bar_color = (255, 0, 0)  # Red
                    pygame.draw.rect(self.screen, bar_color, (sx - bar_w // 2, bar_y, lifetime_w, bar_h))

            # Draw range circle for turrets only (semi-transparent)
            if entity.entity_type == PlacedEntityType.TURRET and hasattr(entity, 'range') and entity.range > 0:
                range_radius = int(entity.range * Config.TILE_SIZE)
                # Draw a faint circle showing turret range
                pygame.draw.circle(self.screen, (255, 100, 100, 50), (sx, sy), range_radius, 1)

            # Draw targeting line if turret has a target
            if entity.entity_type == PlacedEntityType.TURRET and entity.target_enemy and entity.target_enemy.is_alive:
                tx, ty = camera.world_to_screen(Position(entity.target_enemy.position[0], entity.target_enemy.position[1], 0))
                pygame.draw.line(self.screen, (255, 0, 0), (sx, sy), (tx, ty), 2)

        # Render dungeon entrances
        for entrance in world.get_visible_dungeon_entrances(camera.position, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT):
            sx, sy = camera.world_to_screen(entrance.position)
            in_range = character.is_in_range(entrance.position)
            size = Config.TILE_SIZE

            # Get rarity color for the entrance
            rarity_color = entrance.get_rarity_color()

            # Draw entrance as a portal/doorway shape
            # Outer ring with rarity color
            pygame.draw.circle(self.screen, rarity_color, (sx, sy), size // 2, 4)
            # Inner dark circle (portal)
            pygame.draw.circle(self.screen, (30, 30, 40), (sx, sy), size // 2 - 4)
            # Glow effect based on rarity
            glow_color = tuple(min(255, c + 50) for c in rarity_color)
            pygame.draw.circle(self.screen, glow_color, (sx, sy), size // 2 + 2, 2)

            # Highlight when in range
            if in_range:
                pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), size // 2 + 4, 2)

            # Rarity indicator text
            rarity_short = {
                "common": "C", "uncommon": "U", "rare": "R",
                "epic": "E", "legendary": "L", "unique": "!"
            }
            rarity_text = rarity_short.get(entrance.rarity.value, "?")
            rarity_surf = self.small_font.render(rarity_text, True, (255, 255, 255))
            # Black outline for visibility
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.screen.blit(self.small_font.render(rarity_text, True, (0, 0, 0)),
                                 (sx - rarity_surf.get_width() // 2 + dx, sy - rarity_surf.get_height() // 2 + dy))
            self.screen.blit(rarity_surf, (sx - rarity_surf.get_width() // 2, sy - rarity_surf.get_height() // 2))

            # Show "Dungeon" label when in range
            if in_range:
                label = f"{entrance.rarity.value.capitalize()} Dungeon"
                label_surf = self.tiny_font.render(label, True, rarity_color)
                label_bg = pygame.Rect(sx - label_surf.get_width() // 2 - 2, sy - size // 2 - 18,
                                       label_surf.get_width() + 4, label_surf.get_height() + 2)
                pygame.draw.rect(self.screen, (0, 0, 0, 200), label_bg)
                self.screen.blit(label_surf, (sx - label_surf.get_width() // 2, sy - size // 2 - 16))

        for resource in world.get_visible_resources(camera.position, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT):
            if resource.depleted and not resource.respawns:
                continue
            sx, sy = camera.world_to_screen(resource.position)
            in_range = character.is_in_range(resource.position)

            can_harvest, reason = character.can_harvest_resource(resource) if in_range else (False, "")

            size = Config.TILE_SIZE - 4
            rect = pygame.Rect(sx - size // 2, sy - size // 2, size, size)

            # Get icon path from ResourceNodeDatabase (handles name mapping)
            # This maps JSON IDs like 'copper_vein' to existing PNG names like 'copper_ore_node'
            try:
                from data.databases.resource_node_db import ResourceNodeDatabase
                resource_db = ResourceNodeDatabase.get_instance()
                resource_icon_path = resource_db.get_icon_path(resource.resource_type.value)
            except Exception:
                # Fallback to legacy logic if database not available
                resource_value = resource.resource_type.value
                if "tree" not in resource_value and "sapling" not in resource_value:
                    resource_icon_path = f"resources/{resource_value}_node.png"
                else:
                    resource_icon_path = f"resources/{resource_value}.png"

            # Try to load resource icon (only if image cache exists)
            if 'image_cache' not in locals():
                image_cache = ImageCache.get_instance()
            icon = image_cache.get_image(resource_icon_path, (size, size))

            if icon:
                # Render icon
                self.screen.blit(icon, rect.topleft)
            else:
                # Fallback: colored rectangle
                color = resource.get_color() if in_range else tuple(max(0, c - 50) for c in resource.get_color())
                pygame.draw.rect(self.screen, color, rect)

            if in_range:
                border_color = Config.COLOR_CAN_HARVEST if can_harvest else Config.COLOR_CANNOT_HARVEST
                border_width = 3
            else:
                border_color = (0, 0, 0)
                border_width = 2
            pygame.draw.rect(self.screen, border_color, rect, border_width)

            if in_range and not resource.depleted:
                tier_text = f"T{resource.tier}"
                tier_surf = self.tiny_font.render(tier_text, True, (255, 255, 255))
                tier_bg = pygame.Rect(sx - size // 2 + 2, sy - size // 2 + 2,
                                      tier_surf.get_width() + 4, tier_surf.get_height() + 2)
                pygame.draw.rect(self.screen, (0, 0, 0, 180), tier_bg)
                self.screen.blit(tier_surf, (sx - size // 2 + 4, sy - size // 2 + 2))

            if resource.depleted and resource.respawns and in_range:
                progress = resource.get_respawn_progress()
                bar_w, bar_h = Config.TILE_SIZE - 8, 4
                bar_y = sy - Config.TILE_SIZE // 2 - 12
                pygame.draw.rect(self.screen, Config.COLOR_HP_BAR_BG, (sx - bar_w // 2, bar_y, bar_w, bar_h))
                respawn_w = int(bar_w * progress)
                pygame.draw.rect(self.screen, Config.COLOR_RESPAWN_BAR, (sx - bar_w // 2, bar_y, respawn_w, bar_h))
                time_left = int(resource.respawn_timer - resource.time_until_respawn)
                time_surf = self.tiny_font.render(f"{time_left}s", True, (200, 200, 200))
                self.screen.blit(time_surf, (sx - time_surf.get_width() // 2, bar_y - 12))

            elif not resource.depleted and in_range:
                bar_w, bar_h = Config.TILE_SIZE - 8, 4
                bar_y = sy - Config.TILE_SIZE // 2 - 8
                pygame.draw.rect(self.screen, Config.COLOR_HP_BAR_BG, (sx - bar_w // 2, bar_y, bar_w, bar_h))
                hp_w = int(bar_w * (resource.current_hp / resource.max_hp))
                pygame.draw.rect(self.screen, Config.COLOR_HP_BAR, (sx - bar_w // 2, bar_y, hp_w, bar_h))

        # Render enemies
        image_cache = ImageCache.get_instance()
        if combat_manager:
            for enemy in combat_manager.get_all_active_enemies():
                ex, ey = camera.world_to_screen(Position(enemy.position[0], enemy.position[1], 0))

                # Enemy body
                if enemy.is_alive:
                    # Try to load enemy icon
                    size = Config.TILE_SIZE // 2
                    icon = image_cache.get_image(enemy.definition.icon_path, (size * 2, size * 2)) if enemy.definition.icon_path else None

                    if icon:
                        # Render icon centered on enemy position
                        icon_rect = icon.get_rect(center=(ex, ey))
                        self.screen.blit(icon, icon_rect)
                    else:
                        # Fallback: Color based on tier
                        tier_colors = {1: (200, 100, 100), 2: (255, 150, 0), 3: (200, 100, 255), 4: (255, 50, 50)}
                        enemy_color = tier_colors.get(enemy.definition.tier, (200, 100, 100))
                        if enemy.is_boss:
                            enemy_color = (255, 215, 0)  # Gold for bosses

                        pygame.draw.circle(self.screen, enemy_color, (ex, ey), size)
                        pygame.draw.circle(self.screen, (0, 0, 0), (ex, ey), size, 2)

                    # Health bar
                    health_percent = enemy.current_health / enemy.max_health
                    bar_w, bar_h = Config.TILE_SIZE, 4
                    bar_y = ey - Config.TILE_SIZE // 2 - 12
                    pygame.draw.rect(self.screen, Config.COLOR_HP_BAR_BG, (ex - bar_w // 2, bar_y, bar_w, bar_h))
                    hp_w = int(bar_w * health_percent)
                    pygame.draw.rect(self.screen, (255, 0, 0), (ex - bar_w // 2, bar_y, hp_w, bar_h))

                    # Tier indicator
                    tier_text = f"T{enemy.definition.tier}"
                    if enemy.is_boss:
                        tier_text = "BOSS"
                    tier_surf = self.tiny_font.render(tier_text, True, (255, 255, 255))
                    self.screen.blit(tier_surf, (ex - tier_surf.get_width() // 2, ey - 5))

                else:
                    # Corpse (greyed out)
                    corpse_color = (100, 100, 100)
                    size = Config.TILE_SIZE // 3
                    pygame.draw.circle(self.screen, corpse_color, (ex, ey), size)
                    loot_text = self.tiny_font.render("LOOT", True, (255, 255, 0))
                    self.screen.blit(loot_text, (ex - loot_text.get_width() // 2, ey - 10))

        # Render NPCs
        self.render_npcs(camera, character)

        # Render player
        center_x, center_y = camera.world_to_screen(character.position)
        pygame.draw.circle(self.screen, Config.COLOR_PLAYER, (center_x, center_y), Config.TILE_SIZE // 3)

        # Render attack effects (lines, blocked indicators)
        self._render_attack_effects(camera)

        for dmg in damage_numbers:
            sx, sy = camera.world_to_screen(dmg.position)
            alpha = int(255 * (dmg.lifetime / 1.0))
            color = Config.COLOR_DAMAGE_CRIT if dmg.is_crit else Config.COLOR_DAMAGE_NORMAL
            text = f"{dmg.damage}!" if dmg.is_crit else str(dmg.damage)
            surf = (self.font if dmg.is_crit else self.small_font).render(text, True, color)
            surf.set_alpha(alpha)
            self.screen.blit(surf, surf.get_rect(center=(sx, sy)))

    def render_dungeon(self, dungeon_manager, camera: Camera, character,
                       damage_numbers, dungeon_enemies):
        """Render a dungeon instance.

        Args:
            dungeon_manager: DungeonManager instance
            camera: Camera instance
            character: Player character
            damage_numbers: List of damage numbers to display
            dungeon_enemies: List of Enemy instances in the dungeon
        """
        from data.models.world import TileType

        # Fill background
        pygame.draw.rect(self.screen, (30, 30, 40),
                        (0, 0, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT))

        # Get visible tiles
        tiles = dungeon_manager.get_visible_tiles(
            camera.position, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT
        )

        # Render tiles
        for tile in tiles:
            sx, sy = camera.world_to_screen(tile.position)
            if -Config.TILE_SIZE <= sx <= Config.VIEWPORT_WIDTH and -Config.TILE_SIZE <= sy <= Config.VIEWPORT_HEIGHT:
                rect = pygame.Rect(sx, sy, Config.TILE_SIZE, Config.TILE_SIZE)

                # Dungeon-specific tile colors
                if tile.tile_type == TileType.STONE:
                    if not tile.walkable:
                        color = (50, 50, 60)  # Dark wall
                    else:
                        color = (80, 80, 90)  # Stone floor
                elif tile.tile_type == TileType.DIRT:
                    color = (100, 80, 60)  # Dirt patches
                else:
                    color = (70, 70, 80)

                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, (40, 40, 50), rect, 1)

        # Render chest if dungeon is cleared
        dungeon = dungeon_manager.current_dungeon
        if dungeon and dungeon.chest:
            chest = dungeon.chest
            cx, cy = camera.world_to_screen(chest.position)

            # Chest visual
            chest_size = Config.TILE_SIZE - 4
            chest_rect = pygame.Rect(cx - chest_size // 2, cy - chest_size // 2,
                                    chest_size, chest_size)

            if chest.is_opened:
                # Open chest (darker, empty look)
                pygame.draw.rect(self.screen, (100, 70, 40), chest_rect)
                pygame.draw.rect(self.screen, (60, 40, 20), chest_rect, 2)
                # "EMPTY" text
                empty_surf = self.tiny_font.render("EMPTY", True, (150, 150, 150))
                self.screen.blit(empty_surf, (cx - empty_surf.get_width() // 2, cy - 5))
            else:
                # Closed chest (golden, inviting)
                if dungeon.is_cleared:
                    # Glowing effect for available chest
                    glow_rect = chest_rect.inflate(4, 4)
                    pygame.draw.rect(self.screen, (255, 215, 0), glow_rect, 2)

                pygame.draw.rect(self.screen, (180, 130, 50), chest_rect)
                pygame.draw.rect(self.screen, (120, 80, 30), chest_rect, 2)

                # Lock icon if not cleared
                if not dungeon.is_cleared:
                    lock_surf = self.tiny_font.render("🔒", True, (255, 100, 100))
                    self.screen.blit(lock_surf, (cx - lock_surf.get_width() // 2, cy - 5))
                else:
                    open_surf = self.tiny_font.render("LOOT", True, (255, 215, 0))
                    self.screen.blit(open_surf, (cx - open_surf.get_width() // 2, cy - 5))

        # Render exit portal if dungeon is cleared
        if dungeon and dungeon.is_cleared and dungeon.exit_portal_position:
            px, py = camera.world_to_screen(dungeon.exit_portal_position)
            portal_size = Config.TILE_SIZE

            # Animated portal effect (pulsing glow)
            import time
            pulse = 0.5 + 0.5 * abs((time.time() * 2) % 2 - 1)  # 0.5 to 1.0

            # Outer glow
            glow_color = (int(100 * pulse), int(200 * pulse), int(255 * pulse))
            glow_rect = pygame.Rect(px - portal_size // 2 - 4, py - portal_size // 2 - 4,
                                    portal_size + 8, portal_size + 8)
            pygame.draw.ellipse(self.screen, glow_color, glow_rect, 3)

            # Portal circle (blue swirl)
            portal_rect = pygame.Rect(px - portal_size // 2, py - portal_size // 2,
                                      portal_size, portal_size)
            pygame.draw.ellipse(self.screen, (50, 100, 200), portal_rect)
            pygame.draw.ellipse(self.screen, (100, 150, 255), portal_rect, 2)

            # Inner swirl effect
            inner_rect = portal_rect.inflate(-8, -8)
            pygame.draw.ellipse(self.screen, (80, 130, 220), inner_rect)

            # "EXIT" label
            exit_surf = self.tiny_font.render("EXIT", True, (200, 230, 255))
            self.screen.blit(exit_surf, (px - exit_surf.get_width() // 2, py - 5))

        # Render enemies (same as world enemies but for dungeon)
        image_cache = ImageCache.get_instance()
        tier_colors = {
            1: (100, 200, 100),  # Green
            2: (100, 150, 255),  # Blue
            3: (200, 100, 200),  # Purple
            4: (255, 100, 100),  # Red
        }

        for enemy in dungeon_enemies:
            ex, ey = camera.world_to_screen(Position(enemy.position[0], enemy.position[1], 0))

            if -50 <= ex <= Config.VIEWPORT_WIDTH + 50 and -50 <= ey <= Config.VIEWPORT_HEIGHT + 50:
                if enemy.is_alive:
                    size = Config.TILE_SIZE // 2

                    # Try to load enemy PNG icon (same as world enemies)
                    icon = None
                    if enemy.definition.icon_path:
                        icon = image_cache.get_image(enemy.definition.icon_path, (size * 2, size * 2))

                    if icon:
                        # Render icon centered on enemy position
                        icon_rect = icon.get_rect(center=(ex, ey))
                        self.screen.blit(icon, icon_rect)
                    else:
                        # Fallback: Color based on tier
                        enemy_color = tier_colors.get(enemy.definition.tier, (200, 100, 100))
                        if enemy.is_boss:
                            enemy_color = (255, 215, 0)
                            size = Config.TILE_SIZE // 2 + 4

                        pygame.draw.circle(self.screen, enemy_color, (ex, ey), size)
                        pygame.draw.circle(self.screen, (0, 0, 0), (ex, ey), size, 2)

                    # Health bar
                    health_percent = enemy.current_health / enemy.max_health
                    bar_w, bar_h = Config.TILE_SIZE, 4
                    bar_y = ey - size - 8
                    pygame.draw.rect(self.screen, (60, 60, 60), (ex - bar_w // 2, bar_y, bar_w, bar_h))
                    hp_w = int(bar_w * health_percent)
                    pygame.draw.rect(self.screen, (255, 50, 50), (ex - bar_w // 2, bar_y, hp_w, bar_h))

                    # Tier indicator and name
                    tier_text = f"T{enemy.definition.tier}"
                    if enemy.is_boss:
                        tier_text = "BOSS"
                    tier_surf = self.tiny_font.render(tier_text, True, (255, 255, 255))
                    self.screen.blit(tier_surf, (ex - tier_surf.get_width() // 2, ey - 5))
                else:
                    # Corpse (no loot in dungeons - just a grey dot)
                    pygame.draw.circle(self.screen, (80, 80, 80), (ex, ey), Config.TILE_SIZE // 4)

        # Render player
        center_x, center_y = camera.world_to_screen(character.position)
        pygame.draw.circle(self.screen, Config.COLOR_PLAYER, (center_x, center_y), Config.TILE_SIZE // 3)
        pygame.draw.circle(self.screen, (0, 0, 0), (center_x, center_y), Config.TILE_SIZE // 3, 2)

        # Render attack effects (lines, blocked indicators)
        self._render_attack_effects(camera)

        # Render damage numbers
        for dmg in damage_numbers:
            sx, sy = camera.world_to_screen(dmg.position)
            alpha = int(255 * (dmg.lifetime / 1.0))
            color = Config.COLOR_DAMAGE_CRIT if dmg.is_crit else Config.COLOR_DAMAGE_NORMAL
            text = f"{dmg.damage}!" if dmg.is_crit else str(dmg.damage)
            surf = (self.font if dmg.is_crit else self.small_font).render(text, True, color)
            surf.set_alpha(alpha)
            self.screen.blit(surf, surf.get_rect(center=(sx, sy)))

        # Render dungeon UI overlay
        self._render_dungeon_ui(dungeon)

    def _render_dungeon_ui(self, dungeon):
        """Render dungeon-specific UI elements (wave indicator, progress)."""
        if not dungeon:
            return

        # Dungeon rarity text - measure first to calculate panel width
        rarity_colors = {
            "common": (200, 200, 200),
            "uncommon": (100, 255, 100),
            "rare": (100, 150, 255),
            "epic": (200, 100, 255),
            "legendary": (255, 165, 0),
            "unique": (255, 50, 50),
        }
        rarity_name = dungeon.rarity.value.capitalize()
        rarity_color = rarity_colors.get(dungeon.rarity.value, (255, 255, 255))
        rarity_surf = self.font.render(f"{rarity_name} Dungeon", True, rarity_color)

        # Calculate panel width based on text (with padding)
        min_panel_width = 200
        text_padding = 40  # 20px on each side
        panel_width = max(min_panel_width, rarity_surf.get_width() + text_padding)
        panel_height = 80
        panel_x = (Config.VIEWPORT_WIDTH - panel_width) // 2
        panel_y = 10

        # Background panel
        panel_surf = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel_surf.fill((0, 0, 0, 180))
        self.screen.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(self.screen, (100, 100, 100), (panel_x, panel_y, panel_width, panel_height), 2)

        # Render rarity title (already computed)
        self.screen.blit(rarity_surf, (panel_x + (panel_width - rarity_surf.get_width()) // 2, panel_y + 5))

        # Wave indicator
        wave_text = f"Wave {dungeon.current_wave}/{dungeon.total_waves}"
        wave_surf = self.small_font.render(wave_text, True, (255, 255, 255))
        self.screen.blit(wave_surf, (panel_x + (panel_width - wave_surf.get_width()) // 2, panel_y + 30))

        # Progress bar
        progress = dungeon.total_enemies_killed / dungeon.total_mobs if dungeon.total_mobs > 0 else 0
        bar_width = panel_width - 20
        bar_height = 12
        bar_x = panel_x + 10
        bar_y = panel_y + 55

        pygame.draw.rect(self.screen, (60, 60, 60), (bar_x, bar_y, bar_width, bar_height))
        fill_width = int(bar_width * progress)
        pygame.draw.rect(self.screen, (100, 200, 100), (bar_x, bar_y, fill_width, bar_height))
        pygame.draw.rect(self.screen, (100, 100, 100), (bar_x, bar_y, bar_width, bar_height), 1)

        # Progress text
        progress_text = f"{dungeon.total_enemies_killed}/{dungeon.total_mobs}"
        progress_surf = self.tiny_font.render(progress_text, True, (255, 255, 255))
        self.screen.blit(progress_surf, (bar_x + (bar_width - progress_surf.get_width()) // 2, bar_y + 1))

        # Status text
        if dungeon.is_cleared:
            status_text = "CLEARED! Open the chest!"
            status_color = (100, 255, 100)
            status_surf = self.small_font.render(status_text, True, status_color)
            self.screen.blit(status_surf,
                           (panel_x + (panel_width - status_surf.get_width()) // 2, panel_y + panel_height + 5))

    def render_dungeon_chest_ui(self, chest, dungeon_manager) -> Tuple[pygame.Rect, List[Tuple[pygame.Rect, int]]]:
        """Render the dungeon chest UI for item transfer.

        Returns:
            (chest_rect, item_rects) - bounding rect and list of (rect, item_idx) for click detection
        """
        if not chest or not dungeon_manager or not dungeon_manager.in_dungeon:
            return None, []

        # Chest UI position (right side of screen, above inventory)
        ui_width = 250
        ui_height = 300
        ui_x = Config.VIEWPORT_WIDTH - ui_width - 20
        ui_y = Config.VIEWPORT_HEIGHT - Config.INVENTORY_PANEL_HEIGHT - ui_height - 20

        # Background panel
        chest_rect = pygame.Rect(ui_x, ui_y, ui_width, ui_height)
        panel_surf = pygame.Surface((ui_width, ui_height), pygame.SRCALPHA)
        panel_surf.fill((40, 30, 20, 230))
        self.screen.blit(panel_surf, (ui_x, ui_y))

        # Border
        pygame.draw.rect(self.screen, (150, 100, 50), chest_rect, 3)

        # Title
        title_surf = self.font.render("Dungeon Chest", True, (255, 215, 0))
        self.screen.blit(title_surf, (ui_x + (ui_width - title_surf.get_width()) // 2, ui_y + 10))

        # Subtitle
        subtitle_surf = self.tiny_font.render("Click to take items", True, (200, 200, 200))
        self.screen.blit(subtitle_surf, (ui_x + (ui_width - subtitle_surf.get_width()) // 2, ui_y + 35))

        # Item grid
        item_rects = []
        slot_size = 40
        spacing = 5
        slots_per_row = 5
        start_x = ui_x + 15
        start_y = ui_y + 60

        # Get material database for names
        from data.databases.material_db import MaterialDatabase
        from data.databases.equipment_db import EquipmentDatabase
        mat_db = MaterialDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()

        for idx, (item_id, quantity) in enumerate(chest.contents):
            row = idx // slots_per_row
            col = idx % slots_per_row

            slot_x = start_x + col * (slot_size + spacing)
            slot_y = start_y + row * (slot_size + spacing)

            # Only render if in visible area
            if slot_y + slot_size > ui_y + ui_height - 20:
                break

            slot_rect = pygame.Rect(slot_x, slot_y, slot_size, slot_size)

            # Slot background
            pygame.draw.rect(self.screen, (60, 50, 40), slot_rect)
            pygame.draw.rect(self.screen, (100, 80, 60), slot_rect, 2)

            # Item icon (try to get from material/equipment)
            icon = None
            item_name = item_id

            mat = mat_db.get_material(item_id)
            if mat:
                item_name = mat.name if hasattr(mat, 'name') else item_id
                if hasattr(mat, 'icon_path') and mat.icon_path:
                    from rendering.image_cache import ImageCache
                    image_cache = ImageCache.get_instance()
                    icon = image_cache.get_image(mat.icon_path, (slot_size - 8, slot_size - 8))

            if not icon and equip_db.is_equipment(item_id):
                eq = equip_db.get_equipment(item_id)
                if eq:
                    item_name = eq.name if hasattr(eq, 'name') else item_id
                    if hasattr(eq, 'icon_path') and eq.icon_path:
                        from rendering.image_cache import ImageCache
                        image_cache = ImageCache.get_instance()
                        icon = image_cache.get_image(eq.icon_path, (slot_size - 8, slot_size - 8))

            if icon:
                self.screen.blit(icon, (slot_x + 4, slot_y + 4))
            else:
                # Fallback: colored square
                pygame.draw.rect(self.screen, (100, 150, 100), (slot_x + 4, slot_y + 4, slot_size - 8, slot_size - 8))

            # Quantity badge
            if quantity > 1:
                qty_surf = self.tiny_font.render(str(quantity), True, (255, 255, 255))
                qty_bg = pygame.Surface((qty_surf.get_width() + 4, qty_surf.get_height()), pygame.SRCALPHA)
                qty_bg.fill((0, 0, 0, 180))
                self.screen.blit(qty_bg, (slot_x + slot_size - qty_surf.get_width() - 4, slot_y + slot_size - qty_surf.get_height()))
                self.screen.blit(qty_surf, (slot_x + slot_size - qty_surf.get_width() - 2, slot_y + slot_size - qty_surf.get_height()))

            item_rects.append((slot_rect, idx))

        # Instructions at bottom
        hint_surf = self.tiny_font.render("Click inventory to deposit", True, (180, 180, 180))
        self.screen.blit(hint_surf, (ui_x + (ui_width - hint_surf.get_width()) // 2, ui_y + ui_height - 25))

        # Empty chest message
        if not chest.contents:
            empty_surf = self.small_font.render("Chest is empty", True, (150, 150, 150))
            self.screen.blit(empty_surf, (ui_x + (ui_width - empty_surf.get_width()) // 2, ui_y + ui_height // 2))

        return chest_rect, item_rects

    def render_placement_preview(self, camera: Camera, preview_pos):
        """Render placement preview for world item placement mode"""
        if preview_pos:
            sx, sy = camera.world_to_screen(preview_pos)
            size = Config.TILE_SIZE
            rect = pygame.Rect(sx - size // 2, sy - size // 2, size, size)

            # Draw semi-transparent preview
            preview_surface = pygame.Surface((size, size), pygame.SRCALPHA)
            preview_surface.fill((100, 255, 100, 100))  # Green with alpha
            self.screen.blit(preview_surface, rect.topleft)

            # Draw border
            pygame.draw.rect(self.screen, (0, 255, 0), rect, 2)

    def render_day_night_overlay(self, time_phase: str, phase_progress: float):
        """Render day/night cycle visual overlay over the viewport.

        Args:
            time_phase: Current phase ("night", "dawn", "day", "dusk")
            phase_progress: Progress through current phase (0.0 to 1.0)
        """
        # Create overlay surface with alpha
        overlay = pygame.Surface((Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT), pygame.SRCALPHA)

        # Define overlay colors and alpha for each phase
        # Colors are subtle to be "noticeable but not overly dark"
        if time_phase == "night":
            # Deep blue tint, consistent darkness
            base_color = (20, 30, 60)
            alpha = 80  # Moderate darkness
        elif time_phase == "dawn":
            # Transition from night to day: blue-purple to warm orange
            # Interpolate from night to clear
            night_color = (20, 30, 60)
            dawn_color = (80, 50, 30)  # Warm sunrise tint
            r = int(night_color[0] + (dawn_color[0] - night_color[0]) * phase_progress)
            g = int(night_color[1] + (dawn_color[1] - night_color[1]) * phase_progress)
            b = int(night_color[2] + (dawn_color[2] - night_color[2]) * phase_progress)
            base_color = (r, g, b)
            alpha = int(80 - 60 * phase_progress)  # Fade from 80 to 20
        elif time_phase == "day":
            # Very subtle warm tint during day (almost clear)
            base_color = (255, 250, 220)  # Slight warm tint
            alpha = 10  # Almost invisible
        else:  # dusk
            # Transition from day to night: warm orange to deep blue
            dusk_color = (80, 40, 20)  # Warm sunset
            night_color = (20, 30, 60)
            r = int(dusk_color[0] + (night_color[0] - dusk_color[0]) * phase_progress)
            g = int(dusk_color[1] + (night_color[1] - dusk_color[1]) * phase_progress)
            b = int(dusk_color[2] + (night_color[2] - dusk_color[2]) * phase_progress)
            base_color = (r, g, b)
            alpha = int(20 + 60 * phase_progress)  # Fade from 20 to 80

        # Apply overlay
        overlay.fill((*base_color, alpha))
        self.screen.blit(overlay, (0, 0))

        # Draw time indicator in top-left of viewport
        time_names = {"night": "Night", "dawn": "Dawn", "day": "Day", "dusk": "Dusk"}
        time_icons = {"night": "🌙", "dawn": "🌅", "day": "☀️", "dusk": "🌆"}

        # Simple text indicator (without emoji for compatibility)
        time_text = f"{time_names.get(time_phase, 'Day')}"
        text_color = (255, 255, 255) if time_phase in ("night", "dusk") else (40, 40, 40)

        # Background for readability
        text_surf = self.small_font.render(time_text, True, text_color)
        bg_rect = pygame.Rect(8, 8, text_surf.get_width() + 12, text_surf.get_height() + 6)
        bg_surface = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        bg_surface.fill((0, 0, 0, 100) if time_phase in ("night", "dusk") else (255, 255, 255, 100))
        self.screen.blit(bg_surface, bg_rect.topleft)
        self.screen.blit(text_surf, (14, 11))

    def render_ui(self, character: Character, mouse_pos: Tuple[int, int],
                  chunk_info: Optional[Dict[str, Any]] = None):
        """Render the character info UI panel.

        Args:
            character: Player character
            mouse_pos: Current mouse position
            chunk_info: Optional dict with 'name', 'danger_level' for current chunk
        """
        ui_rect = pygame.Rect(Config.VIEWPORT_WIDTH, 0, Config.UI_PANEL_WIDTH, Config.VIEWPORT_HEIGHT)
        pygame.draw.rect(self.screen, Config.COLOR_UI_BG, ui_rect)

        y = 20

        # Debug mode indicator
        if Config.DEBUG_INFINITE_RESOURCES:
            debug_surf = self.font.render("DEBUG MODE", True, (255, 100, 100))
            self.screen.blit(debug_surf, (Config.VIEWPORT_WIDTH + 20, y))
            y += 30

        self.render_text("CHARACTER INFO", Config.VIEWPORT_WIDTH + 20, y, bold=True)
        y += 40

        if character.class_system.current_class:
            # Try to load class icon
            class_id = character.class_system.current_class.class_id
            class_icon_path = f"classes/{class_id}.png"
            image_cache = ImageCache.get_instance()
            class_icon = image_cache.get_image(class_icon_path, (24, 24))

            if class_icon:
                # Render icon next to text
                self.screen.blit(class_icon, (Config.VIEWPORT_WIDTH + 20, y - 2))
                class_text = f"Class: {character.class_system.current_class.name}"
                self.render_text(class_text, Config.VIEWPORT_WIDTH + 50, y, small=True)
            else:
                # Fallback without icon
                class_text = f"Class: {character.class_system.current_class.name}"
                self.render_text(class_text, Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 25

        self.render_text(f"Position: ({character.position.x:.1f}, {character.position.y:.1f})",
                         Config.VIEWPORT_WIDTH + 20, y, small=True)
        y += 20

        # Display current chunk name with color based on danger level
        if chunk_info:
            chunk_name = chunk_info.get('name', 'Unknown')
            danger_level = chunk_info.get('danger_level', 'peaceful')

            # Color based on danger level
            chunk_colors = {
                'peaceful': (100, 200, 100),   # Green - safe
                'dangerous': (255, 165, 0),    # Orange - caution
                'rare': (180, 100, 255),       # Purple - rare/special
                'water': (100, 180, 255),      # Blue - water
            }
            chunk_color = chunk_colors.get(danger_level, (180, 180, 180))

            chunk_surf = self.small_font.render(f"Chunk: {chunk_name}", True, chunk_color)
            self.screen.blit(chunk_surf, (Config.VIEWPORT_WIDTH + 20, y))
            y += 25
        else:
            y += 5

        lvl_text = f"Level: {character.leveling.level}"
        if character.leveling.unallocated_stat_points > 0:
            lvl_text += f" ({character.leveling.unallocated_stat_points} pts!)"
        self.render_text(lvl_text, Config.VIEWPORT_WIDTH + 20, y, small=True)
        y += 20

        exp_needed = character.leveling.get_exp_for_next_level()
        if exp_needed > 0:
            self.render_text(f"XP: {character.leveling.current_exp}/{exp_needed}",
                             Config.VIEWPORT_WIDTH + 20, y, small=True)
        else:
            self.render_text("MAX LEVEL", Config.VIEWPORT_WIDTH + 20, y, small=True)
        y += 30

        self.render_health_bar(character, Config.VIEWPORT_WIDTH + 20, y)
        y += 35
        self.render_mana_bar(character, Config.VIEWPORT_WIDTH + 20, y)
        y += 30

        # Render active buffs
        y = self.render_active_buffs(character, Config.VIEWPORT_WIDTH + 20, y)
        y += 10

        self.render_text("SELECTED TOOL", Config.VIEWPORT_WIDTH + 20, y, bold=True)
        y += 30
        if character.selected_tool:
            tool = character.selected_tool
            # Try to show tool icon (tools are equipment items)
            from data.databases import EquipmentDatabase
            equip_db = EquipmentDatabase.get_instance()
            equipment = equip_db.create_equipment_from_id(tool.tool_id)
            if equipment and equipment.icon_path:
                image_cache = ImageCache.get_instance()
                icon = image_cache.get_image(equipment.icon_path, (32, 32))
                if icon:
                    self.screen.blit(icon, (Config.VIEWPORT_WIDTH + 20, y - 2))
                    self.render_text(f"{tool.name} (T{tool.tier})", Config.VIEWPORT_WIDTH + 58, y, small=True)
                    y += 20
                else:
                    self.render_text(f"{tool.name} (T{tool.tier})", Config.VIEWPORT_WIDTH + 20, y, small=True)
                    y += 20
            else:
                self.render_text(f"{tool.name} (T{tool.tier})", Config.VIEWPORT_WIDTH + 20, y, small=True)
                y += 20
            dur_text = f"Durability: {tool.durability_current}/{tool.durability_max}"
            if Config.DEBUG_INFINITE_DURABILITY:
                dur_text += " (∞)"
            self.render_text(dur_text, Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 20
            self.render_text(f"Effectiveness: {tool.get_effectiveness() * 100:.0f}%",
                             Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 30

        title_count = len(character.titles.earned_titles)
        self.render_text(f"TITLES: {title_count}", Config.VIEWPORT_WIDTH + 20, y, bold=True)
        y += 30

        # Show last 3 earned titles with icons
        image_cache = ImageCache.get_instance()
        for title in character.titles.earned_titles[-3:]:
            # Try to render icon
            if title.icon_path:
                icon = image_cache.get_image(title.icon_path, (24, 24))
                if icon:
                    self.screen.blit(icon, (Config.VIEWPORT_WIDTH + 20, y - 2))
                    self.render_text(title.name, Config.VIEWPORT_WIDTH + 50, y, small=True)
                else:
                    self.render_text(f"• {title.name}", Config.VIEWPORT_WIDTH + 20, y, small=True)
            else:
                self.render_text(f"• {title.name}", Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 28

        if title_count > 0:
            y += 5

        self.render_text("CONTROLS", Config.VIEWPORT_WIDTH + 20, y, bold=True)
        y += 30
        controls = [
            "WASD - Move",
            "CLICK - Harvest/Interact",
            "TAB - Switch tool",
            "1-5 - Use skills",
            "C - Stats",
            "E - Equipment",
            "K - Skills menu",
            "M - Map",
            "L - Encyclopedia",
            "F1 - Debug Mode",
            "ESC - Close/Quit"
        ]
        for ctrl in controls:
            self.render_text(ctrl, Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 22

    def render_health_bar(self, char, x, y):
        w, h = 300, 25
        pygame.draw.rect(self.screen, Config.COLOR_HEALTH_BG, (x, y, w, h))
        hp_w = int(w * (char.health / char.max_health))
        pygame.draw.rect(self.screen, Config.COLOR_HEALTH, (x, y, hp_w, h))
        pygame.draw.rect(self.screen, Config.COLOR_TEXT, (x, y, w, h), 2)
        text = self.small_font.render(f"HP: {char.health}/{char.max_health}", True, Config.COLOR_TEXT)
        self.screen.blit(text, text.get_rect(center=(x + w // 2, y + h // 2)))

    def render_mana_bar(self, char, x, y):
        w, h = 300, 20
        pygame.draw.rect(self.screen, Config.COLOR_HEALTH_BG, (x, y, w, h))
        mana_w = int(w * (char.mana / char.max_mana))
        pygame.draw.rect(self.screen, (50, 150, 255), (x, y, mana_w, h))
        pygame.draw.rect(self.screen, Config.COLOR_TEXT, (x, y, w, h), 2)
        text = self.small_font.render(f"MP: {int(char.mana)}/{int(char.max_mana)}", True, Config.COLOR_TEXT)
        self.screen.blit(text, text.get_rect(center=(x + w // 2, y + h // 2)))

    def render_active_buffs(self, character: Character, x: int, y: int) -> int:
        """
        Render active buffs with icons and timers
        Returns the Y position after rendering all buffs
        """
        if not character.buffs.active_buffs:
            return y

        # Title
        self.render_text("ACTIVE BUFFS", x, y, bold=True)
        y += 25

        for buff in character.buffs.active_buffs:
            # Buff name and timer - FIXED: use duration_remaining (not remaining_duration)
            time_left = buff.duration_remaining
            mins = int(time_left // 60)
            secs = int(time_left % 60)
            time_str = f"{mins}:{secs:02d}" if mins > 0 else f"{secs}s"

            # Color based on buff category
            color = (100, 255, 100) if buff.category == "combat" else (100, 200, 255)

            # Draw buff bar
            bar_width = 300
            bar_height = 18
            pygame.draw.rect(self.screen, (40, 40, 50), (x, y, bar_width, bar_height))

            # Fill based on remaining time - FIXED: use get_progress_percent() method
            fill_width = int(bar_width * buff.get_progress_percent())
            pygame.draw.rect(self.screen, color, (x, y, fill_width, bar_height))
            pygame.draw.rect(self.screen, (150, 150, 150), (x, y, bar_width, bar_height), 1)

            # Buff name and time
            buff_text = self.tiny_font.render(f"{buff.name}: {time_str}", True, (255, 255, 255))
            # Black outline for readability
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.screen.blit(self.tiny_font.render(f"{buff.name}: {time_str}", True, (0, 0, 0)),
                                (x + 5 + dx, y + 2 + dy))
            self.screen.blit(buff_text, (x + 5, y + 2))

            y += bar_height + 3

        return y + 10

    def render_skill_hotbar(self, character: Character):
        """Render skill hotbar at bottom center of screen"""
        slot_size = 60
        slot_spacing = 10
        num_slots = 5
        total_width = num_slots * slot_size + (num_slots - 1) * slot_spacing

        # Position at bottom center
        start_x = (Config.VIEWPORT_WIDTH - total_width) // 2
        start_y = Config.VIEWPORT_HEIGHT - slot_size - 20

        skill_db = SkillDatabase.get_instance()
        hovered_skill = None
        hovered_slot_rect = None

        for i in range(num_slots):
            x = start_x + i * (slot_size + slot_spacing)
            y = start_y

            # Slot background
            slot_rect = pygame.Rect(x, y, slot_size, slot_size)
            pygame.draw.rect(self.screen, (30, 30, 40), slot_rect)
            pygame.draw.rect(self.screen, (100, 100, 120), slot_rect, 2)

            # Key number
            key_text = self.small_font.render(str(i + 1), True, (150, 150, 150))
            self.screen.blit(key_text, (x + 4, y + 4))

            # Get equipped skill in this slot
            skill_id = character.skills.equipped_skills[i]
            if skill_id:
                player_skill = character.skills.known_skills.get(skill_id)
                if player_skill:
                    skill_def = player_skill.get_definition()
                    if skill_def:
                        # Check hover
                        mouse_pos = pygame.mouse.get_pos()
                        if slot_rect.collidepoint(mouse_pos):
                            hovered_skill = (skill_def, player_skill)
                            hovered_slot_rect = slot_rect

                        # Try to display skill icon
                        icon_displayed = False
                        if skill_def.icon_path:
                            from rendering.image_cache import ImageCache
                            image_cache = ImageCache.get_instance()
                            icon_size = slot_size - 16  # Leave room for key number and mana cost
                            icon = image_cache.get_image(skill_def.icon_path, (icon_size, icon_size))
                            if icon:
                                icon_x = x + 8
                                icon_y = y + 8
                                self.screen.blit(icon, (icon_x, icon_y))
                                icon_displayed = True

                        # Fallback to abbreviated name if no icon
                        if not icon_displayed:
                            name_parts = skill_def.name.split()
                            short_name = "".join(p[0] for p in name_parts[:2])  # First letters
                            name_surf = self.font.render(short_name, True, (200, 200, 255))
                            name_rect = name_surf.get_rect(center=(x + slot_size // 2, y + slot_size // 2 - 5))
                            self.screen.blit(name_surf, name_rect)

                        # Cooldown overlay
                        if player_skill.current_cooldown > 0:
                            # Dark overlay
                            overlay = pygame.Surface((slot_size, slot_size), pygame.SRCALPHA)
                            overlay.fill((0, 0, 0, 180))
                            self.screen.blit(overlay, (x, y))

                            # Cooldown timer
                            cd_text = self.small_font.render(f"{player_skill.current_cooldown:.1f}s", True, (255, 100, 100))
                            cd_rect = cd_text.get_rect(center=(x + slot_size // 2, y + slot_size // 2))
                            self.screen.blit(cd_text, cd_rect)
                        else:
                            # Mana cost
                            mana_cost = skill_db.get_mana_cost(skill_def.cost.mana)
                            cost_color = (100, 200, 255) if character.mana >= mana_cost else (255, 100, 100)
                            cost_text = self.tiny_font.render(f"{mana_cost}MP", True, cost_color)
                            self.screen.blit(cost_text, (x + 4, y + slot_size - 14))
            else:
                # Empty slot
                empty_text = self.tiny_font.render("Empty", True, (80, 80, 80))
                empty_rect = empty_text.get_rect(center=(x + slot_size // 2, y + slot_size // 2))
                self.screen.blit(empty_text, empty_rect)

        # Render tooltip for hovered skill
        if hovered_skill:
            self._render_skill_tooltip(hovered_skill[0], hovered_skill[1], hovered_slot_rect, character)

    def _render_skill_tooltip(self, skill_def, player_skill, slot_rect, character):
        """Render tooltip for a skill"""
        skill_db = SkillDatabase.get_instance()

        # Tooltip dimensions
        tooltip_width = 350
        tooltip_height = 200
        padding = 10

        # Position above the slot
        tooltip_x = slot_rect.centerx - tooltip_width // 2
        tooltip_y = slot_rect.y - tooltip_height - 10

        # Keep on screen
        tooltip_x = max(10, min(tooltip_x, Config.VIEWPORT_WIDTH - tooltip_width - 10))
        tooltip_y = max(10, tooltip_y)

        # Background
        surf = pygame.Surface((tooltip_width, tooltip_height), pygame.SRCALPHA)
        surf.fill((25, 25, 35, 250))
        pygame.draw.rect(surf, (100, 150, 200), surf.get_rect(), 2)

        y = padding

        # Skill name
        name_surf = self.font.render(skill_def.name, True, (200, 220, 255))
        surf.blit(name_surf, (padding, y))
        y += 25

        # Tier and rarity
        tier_text = f"Tier {skill_def.tier} - {skill_def.rarity.upper()}"
        tier_color = {1: (150, 150, 150), 2: (100, 200, 100), 3: (200, 100, 200), 4: (255, 200, 50)}.get(skill_def.tier, (150, 150, 150))
        surf.blit(self.small_font.render(tier_text, True, tier_color), (padding, y))
        y += 20

        # Cost and cooldown
        mana_cost = skill_db.get_mana_cost(skill_def.cost.mana)
        cooldown = skill_db.get_cooldown_seconds(skill_def.cost.cooldown)
        cost_text = f"Cost: {mana_cost} MP  |  Cooldown: {cooldown}s"
        surf.blit(self.small_font.render(cost_text, True, (150, 200, 255)), (padding, y))
        y += 25

        # Effect
        effect_text = f"{skill_def.effect.effect_type.capitalize()} - {skill_def.effect.category} ({skill_def.effect.magnitude})"
        surf.blit(self.small_font.render(effect_text, True, (200, 200, 100)), (padding, y))
        y += 20

        # Description (word-wrapped)
        desc_words = skill_def.description.split()
        line = ""
        for word in desc_words:
            test_line = line + word + " "
            if self.tiny_font.size(test_line)[0] > tooltip_width - 2 * padding:
                surf.blit(self.tiny_font.render(line, True, (180, 180, 180)), (padding, y))
                y += 16
                line = word + " "
            else:
                line = test_line
        if line:
            surf.blit(self.tiny_font.render(line, True, (180, 180, 180)), (padding, y))

        self.screen.blit(surf, (tooltip_x, tooltip_y))

    def render_skills_menu_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        """Render skills menu for managing equipped skills"""
        if not character.skills_ui_open:
            return None

        skill_db = SkillDatabase.get_instance()
        if not skill_db.loaded:
            return None

        s = Config.scale  # Shorthand for readability
        ww, wh = Config.MENU_LARGE_W, Config.MENU_LARGE_H
        wx = max(0, (Config.VIEWPORT_WIDTH - ww) // 2)  # Clamp to prevent off-screen
        wy = s(50)

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 245))

        # Title
        surf.blit(self.font.render("SKILLS MANAGEMENT", True, (150, 200, 255)), (ww // 2 - s(120), s(20)))
        surf.blit(self.small_font.render("[ESC] Close | [Mouse Wheel] Scroll | Click to equip | Right-click to unequip", True, (180, 180, 180)),
                  (ww // 2 - s(330), s(50)))

        # Hotbar section (top)
        y_pos = s(90)
        surf.blit(self.small_font.render("SKILL HOTBAR (1-5):", True, (200, 200, 200)), (s(20), y_pos))
        y_pos += s(30)

        hotbar_rects = []
        slot_size = s(70)
        for i in range(5):
            x = s(30) + i * (slot_size + s(10))
            slot_rect = pygame.Rect(x, y_pos, slot_size, slot_size)

            # Get skill in this slot
            skill_id = character.skills.equipped_skills[i]
            player_skill = character.skills.known_skills.get(skill_id) if skill_id else None
            skill_def = player_skill.get_definition() if player_skill else None

            # Slot background
            bg_color = (50, 70, 90) if skill_def else (40, 40, 50)
            pygame.draw.rect(surf, bg_color, slot_rect)
            pygame.draw.rect(surf, (100, 150, 200), slot_rect, 2)

            # Slot number
            num_surf = self.small_font.render(str(i + 1), True, (150, 150, 150))
            surf.blit(num_surf, (x + s(4), y_pos + s(4)))

            if skill_def:
                # Try to load skill icon
                if skill_def.icon_path:
                    image_cache = ImageCache.get_instance()
                    icon = image_cache.get_image(skill_def.icon_path, (slot_size - s(16), slot_size - s(16)))
                    if icon:
                        icon_x = x + s(8)
                        icon_y = y_pos + s(8)
                        surf.blit(icon, (icon_x, icon_y))
                    else:
                        # Fallback: Skill abbreviation
                        name_parts = skill_def.name.split()
                        short_name = "".join(p[0] for p in name_parts[:2])
                        name_surf = self.font.render(short_name, True, (200, 220, 255))
                        name_rect = name_surf.get_rect(center=(x + slot_size // 2, y_pos + slot_size // 2))
                        surf.blit(name_surf, name_rect)
                else:
                    # Fallback: Skill abbreviation
                    name_parts = skill_def.name.split()
                    short_name = "".join(p[0] for p in name_parts[:2])
                    name_surf = self.font.render(short_name, True, (200, 220, 255))
                    name_rect = name_surf.get_rect(center=(x + slot_size // 2, y_pos + slot_size // 2))
                    surf.blit(name_surf, name_rect)

            hotbar_rects.append((slot_rect, i, skill_id))

        y_pos += slot_size + s(30)

        # Learned skills section
        total_skills = len(character.skills.known_skills)
        surf.blit(self.small_font.render(f"LEARNED SKILLS ({total_skills}):", True, (200, 200, 200)), (s(20), y_pos))
        y_pos += s(30)

        skill_rects = []
        max_visible = 10

        # Calculate scroll bounds
        max_scroll = max(0, total_skills - max_visible)
        character.skills_menu_scroll_offset = max(0, min(character.skills_menu_scroll_offset, max_scroll))

        # Get skills to display based on scroll offset
        all_skills = list(character.skills.known_skills.items())
        visible_skills = all_skills[character.skills_menu_scroll_offset:character.skills_menu_scroll_offset + max_visible]

        # Show scroll indicator if needed
        if total_skills > max_visible:
            scroll_text = f"[Scroll: {character.skills_menu_scroll_offset + 1}-{min(character.skills_menu_scroll_offset + max_visible, total_skills)} of {total_skills}]"
            surf.blit(self.tiny_font.render(scroll_text, True, (150, 150, 200)), (ww - s(280), y_pos - s(25)))

        for idx, (skill_id, player_skill) in enumerate(visible_skills):
            skill_def = player_skill.get_definition()
            if not skill_def:
                continue

            # Check if equipped
            equipped_slot = None
            for slot_idx, equipped_id in enumerate(character.skills.equipped_skills):
                if equipped_id == skill_id:
                    equipped_slot = slot_idx
                    break

            skill_rect = pygame.Rect(s(20), y_pos, ww - s(40), s(50))
            rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
            is_hovered = skill_rect.collidepoint(rx, ry)

            # Background
            bg_color = (70, 90, 60) if equipped_slot is not None else (50, 50, 70)
            if is_hovered:
                bg_color = tuple(min(255, c + 20) for c in bg_color)
            pygame.draw.rect(surf, bg_color, skill_rect)
            pygame.draw.rect(surf, (120, 140, 180) if is_hovered else (80, 80, 100), skill_rect, 2)

            # Skill icon (if available)
            text_x_offset = s(30)
            if skill_def.icon_path:
                image_cache = ImageCache.get_instance()
                icon = image_cache.get_image(skill_def.icon_path, (s(40), s(40)))
                if icon:
                    surf.blit(icon, (s(25), y_pos + s(5)))
                    text_x_offset = s(70)

            # Skill name
            surf.blit(self.small_font.render(skill_def.name, True, (255, 255, 255)), (text_x_offset, y_pos + s(5)))

            # Tier and rarity
            tier_color = {1: (150, 150, 150), 2: (100, 200, 100), 3: (200, 100, 200), 4: (255, 200, 50)}.get(skill_def.tier, (150, 150, 150))
            surf.blit(self.tiny_font.render(f"T{skill_def.tier} {skill_def.rarity.upper()}", True, tier_color), (text_x_offset, y_pos + s(25)))

            # Mana cost and cooldown
            mana_cost = skill_db.get_mana_cost(skill_def.cost.mana)
            cooldown = skill_db.get_cooldown_seconds(skill_def.cost.cooldown)
            surf.blit(self.tiny_font.render(f"{mana_cost}MP  |  {cooldown}s CD", True, (150, 200, 255)), (s(200), y_pos + s(25)))

            # Equipped indicator
            if equipped_slot is not None:
                surf.blit(self.small_font.render(f"[Slot {equipped_slot + 1}]", True, (100, 255, 100)), (ww - s(150), y_pos + s(15)))
            else:
                surf.blit(self.tiny_font.render("Click to equip", True, (120, 120, 150)), (ww - s(150), y_pos + s(18)))

            skill_rects.append((skill_rect, skill_id, player_skill, skill_def))
            y_pos += s(55)

        # Available skills section (skills that can be learned but haven't been yet)
        y_pos += s(10)
        available_skill_ids = character.skills.get_available_skills(character)
        available_skill_rects = []

        if available_skill_ids:
            surf.blit(self.small_font.render(f"AVAILABLE TO LEARN ({len(available_skill_ids)}):", True, (100, 255, 100)), (s(20), y_pos))
            y_pos += s(25)

            for skill_id in available_skill_ids[:3]:  # Show first 3 available skills
                skill_def = skill_db.skills.get(skill_id)
                if not skill_def:
                    continue

                skill_rect = pygame.Rect(s(20), y_pos, ww - s(40), s(45))
                rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
                is_hovered = skill_rect.collidepoint(rx, ry)

                # Background
                bg_color = (40, 80, 40)
                if is_hovered:
                    bg_color = (60, 120, 60)
                pygame.draw.rect(surf, bg_color, skill_rect)
                pygame.draw.rect(surf, (100, 255, 100) if is_hovered else (80, 150, 80), skill_rect, 2)

                # Skill icon (if available) - with greyscale effect for unlearned
                text_x_offset = s(30)
                if skill_def.icon_path:
                    image_cache = ImageCache.get_instance()
                    icon = image_cache.get_image(skill_def.icon_path, (s(35), s(35)))
                    if icon:
                        surf.blit(icon, (s(25), y_pos + s(5)))
                        text_x_offset = s(65)

                # Skill name
                surf.blit(self.small_font.render(skill_def.name, True, (200, 255, 200)), (text_x_offset, y_pos + s(5)))

                # Tier
                tier_color = {1: (150, 150, 150), 2: (100, 200, 100), 3: (200, 100, 200), 4: (255, 200, 50)}.get(skill_def.tier, (150, 150, 150))
                surf.blit(self.tiny_font.render(f"T{skill_def.tier}", True, tier_color), (text_x_offset, y_pos + s(25)))

                # Learn button
                surf.blit(self.tiny_font.render("Click to learn", True, (150, 255, 150)), (ww - s(150), y_pos + s(15)))

                available_skill_rects.append((skill_rect, skill_id, skill_def))
                y_pos += s(50)

            if len(available_skill_ids) > 3:
                surf.blit(self.tiny_font.render(f"...and {len(available_skill_ids) - 3} more available", True, (120, 200, 120)), (s(30), y_pos))

        self.screen.blit(surf, (wx, wy))
        window_rect = pygame.Rect(wx, wy, ww, wh)
        return window_rect, hotbar_rects, skill_rects, available_skill_rects

    def render_encyclopedia_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        """Render encyclopedia/compendium UI"""
        if not character.encyclopedia.is_open:
            return None

        s = Config.scale  # Shorthand for scaling
        ww, wh = Config.MENU_LARGE_W, Config.MENU_LARGE_H
        wx = max(0, (Config.VIEWPORT_WIDTH - ww) // 2)  # Clamp to prevent off-screen
        wy = s(40)

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        # Title
        surf.blit(self.font.render("ENCYCLOPEDIA", True, (255, 215, 0)), (ww // 2 - s(80), s(20)))
        surf.blit(self.small_font.render("[L or ESC] Close | [Mouse Wheel] Scroll", True, (180, 180, 180)),
                  (ww // 2 - s(160), s(50)))

        # Tabs - adjusted for 6 tabs
        tab_y = s(80)
        tab_width = s(115)  # Reduced from 140 to fit 6 tabs
        tab_height = s(40)
        tab_spacing = s(8)  # Reduced spacing
        tabs = [
            ("guide", "GAME GUIDE"),
            ("quests", "QUESTS"),
            ("skills", "SKILLS"),
            ("titles", "TITLES"),
            ("stats", "STATS"),
            ("recipes", "INVENTIONS")
        ]

        tab_rects = []
        for idx, (tab_id, tab_name) in enumerate(tabs):
            tab_x = s(30) + idx * (tab_width + tab_spacing)
            tab_rect = pygame.Rect(tab_x, tab_y, tab_width, tab_height)

            is_active = character.encyclopedia.current_tab == tab_id
            rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
            is_hovered = tab_rect.collidepoint(rx, ry)

            # Tab background
            if is_active:
                bg_color = (80, 80, 120)
                border_color = (150, 150, 200)
            elif is_hovered:
                bg_color = (60, 60, 90)
                border_color = (120, 120, 160)
            else:
                bg_color = (40, 40, 60)
                border_color = (80, 80, 100)

            pygame.draw.rect(surf, bg_color, tab_rect)
            pygame.draw.rect(surf, border_color, tab_rect, s(2))

            # Tab text
            text_surf = self.small_font.render(tab_name, True, (220, 220, 240) if is_active else (160, 160, 180))
            text_rect = text_surf.get_rect(center=tab_rect.center)
            surf.blit(text_surf, text_rect)

            tab_rects.append((tab_rect, tab_id))

        # Content area
        content_y = tab_y + tab_height + s(20)
        content_height = wh - content_y - s(20)
        content_rect = pygame.Rect(s(20), content_y, ww - s(40), content_height)
        pygame.draw.rect(surf, (30, 30, 40), content_rect)
        pygame.draw.rect(surf, (80, 80, 100), content_rect, s(2))

        # Render content based on current tab
        if character.encyclopedia.current_tab == "guide":
            self._render_guide_content(surf, content_rect, character)
        elif character.encyclopedia.current_tab == "quests":
            self._render_quests_content(surf, content_rect, character)
        elif character.encyclopedia.current_tab == "skills":
            self._render_skills_content(surf, content_rect, character)
        elif character.encyclopedia.current_tab == "titles":
            self._render_titles_content(surf, content_rect, character)
        elif character.encyclopedia.current_tab == "stats":
            self._render_stats_content(surf, content_rect, character)
        elif character.encyclopedia.current_tab == "recipes":
            self._render_recipes_content(surf, content_rect, character)

        self.screen.blit(surf, (wx, wy))
        window_rect = pygame.Rect(wx, wy, ww, wh)
        self.encyclopedia_window_rect = window_rect  # Store for mouse wheel scrolling
        return window_rect, tab_rects

    def render_map_ui(self, character: Character, map_system, world_system,
                      mouse_pos: Tuple[int, int], game_time: float = 0.0,
                      rename_state: Optional[Tuple[int, str]] = None,
                      delete_confirm_slot: int = -1):
        """Render the world map UI with explored chunks and waypoints.

        Args:
            character: Player character (for position and level)
            map_system: MapWaypointSystem instance
            world_system: WorldSystem instance (for biome info)
            mouse_pos: Current mouse position
            game_time: Current game time for cooldown display
            rename_state: Tuple of (slot, current_text) if renaming, else None
            delete_confirm_slot: Slot index pending delete confirmation, or -1

        Returns:
            Tuple of (window_rect, map_area_rect, waypoint_rects, action_rects) for click detection
        """
        import math

        if not map_system.map_open:
            return None

        config = MapWaypointConfig.get_instance()
        s = Config.scale

        # Window dimensions
        ww, wh = s(config.ui.map_window_size[0]), s(config.ui.map_window_size[1])
        wx = max(0, (Config.VIEWPORT_WIDTH - ww) // 2)
        wy = s(40)

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        bg_color = config.ui.background_color
        surf.fill(bg_color)

        # Title bar
        title_text = f"WORLD MAP - Explored: {map_system.get_explored_count()} chunks"
        surf.blit(self.font.render(title_text, True, (255, 215, 0)), (s(20), s(15)))

        # Controls hint
        controls = "[M/ESC] Close | [Scroll] Zoom | [Drag] Pan map | [P] Place waypoint"
        surf.blit(self.small_font.render(controls, True, (180, 180, 180)), (s(20), s(40)))

        # Zoom indicator
        zoom_text = f"Zoom: {map_system.map_zoom:.1f}x"
        surf.blit(self.small_font.render(zoom_text, True, (150, 200, 255)), (ww - s(100), s(15)))

        # Map area dimensions
        waypoint_panel_w = s(config.ui.waypoint_panel_width)
        map_area_x = s(10)
        map_area_y = s(60)
        map_area_w = ww - waypoint_panel_w - s(30)
        map_area_h = wh - s(80)

        # Draw map background
        map_rect = pygame.Rect(map_area_x, map_area_y, map_area_w, map_area_h)
        pygame.draw.rect(surf, (15, 15, 25), map_rect)
        pygame.draw.rect(surf, tuple(config.ui.border_color), map_rect, s(2))

        # Calculate chunk rendering parameters
        chunk_size = s(config.map_display.chunk_render_size) * map_system.map_zoom
        chunk_size = max(s(4), int(chunk_size))  # Minimum size

        # Get player chunk position
        player_chunk_x = math.floor(character.position.x) // Config.CHUNK_SIZE
        player_chunk_y = math.floor(character.position.y) // Config.CHUNK_SIZE

        # Center on player if configured, otherwise use scroll position
        if config.map_display.center_on_player:
            center_chunk_x = player_chunk_x - map_system.map_scroll_x
            center_chunk_y = player_chunk_y - map_system.map_scroll_y
        else:
            center_chunk_x = map_system.map_scroll_x
            center_chunk_y = map_system.map_scroll_y

        # Calculate visible chunk range
        visible_chunks_x = int(map_area_w / chunk_size) + 2
        visible_chunks_y = int(map_area_h / chunk_size) + 2

        start_chunk_x = int(center_chunk_x - visible_chunks_x // 2)
        start_chunk_y = int(center_chunk_y - visible_chunks_y // 2)

        # Map center in pixels (relative to map_rect)
        map_center_x = map_area_w // 2
        map_center_y = map_area_h // 2

        # Render chunks
        hovered_chunk = None
        for dy in range(-visible_chunks_y // 2, visible_chunks_y // 2 + 1):
            for dx in range(-visible_chunks_x // 2, visible_chunks_x // 2 + 1):
                chunk_x = int(center_chunk_x) + dx
                chunk_y = int(center_chunk_y) + dy

                # Calculate pixel position on map
                px = map_area_x + map_center_x + int((chunk_x - center_chunk_x) * chunk_size)
                py = map_area_y + map_center_y + int((chunk_y - center_chunk_y) * chunk_size)

                # Skip if outside map area
                if px + chunk_size < map_area_x or px > map_area_x + map_area_w:
                    continue
                if py + chunk_size < map_area_y or py > map_area_y + map_area_h:
                    continue

                # Get chunk color based on exploration status
                explored = map_system.get_explored_chunk(chunk_x, chunk_y)
                if explored:
                    chunk_type = explored.chunk_type.lower().replace(' ', '_')
                    color = config.get_biome_color(chunk_type)
                else:
                    color = config.biome_colors.get('unexplored', (30, 30, 40))

                # Draw chunk
                chunk_rect = pygame.Rect(px, py, chunk_size - 1, chunk_size - 1)
                pygame.draw.rect(surf, color, chunk_rect)

                # At high zoom, add subtle texture to explored chunks
                if explored and map_system.map_zoom >= 1.5 and chunk_size >= s(20):
                    # Add subtle grid lines within chunk to show tiles (every 4 tiles)
                    tile_grid_color = tuple(max(0, c - 20) for c in color)
                    tile_divisions = 4  # Show 4x4 sub-grid
                    sub_size = chunk_size // tile_divisions
                    for i in range(1, tile_divisions):
                        # Vertical line
                        lx = px + i * sub_size
                        pygame.draw.line(surf, tile_grid_color, (lx, py + 2), (lx, py + chunk_size - 3), 1)
                        # Horizontal line
                        ly = py + i * sub_size
                        pygame.draw.line(surf, tile_grid_color, (px + 2, ly), (px + chunk_size - 3, ly), 1)

                # Show chunk coordinates when zoomed in
                if explored and map_system.map_zoom >= 2.0 and chunk_size >= s(30):
                    coord_label = f"{chunk_x},{chunk_y}"
                    coord_surf = self.small_font.render(coord_label, True, (255, 255, 255, 180))
                    label_x = px + (chunk_size - coord_surf.get_width()) // 2
                    label_y = py + (chunk_size - coord_surf.get_height()) // 2
                    surf.blit(coord_surf, (label_x, label_y))

                # Highlight spawn area
                if chunk_x == 0 and chunk_y == 0:
                    pygame.draw.rect(surf, config.biome_colors.get('spawn_area', (255, 215, 0)), chunk_rect, s(2))

                # Draw dungeon marker
                if explored and explored.has_dungeon:
                    dungeon_color = config.dungeon_marker.color
                    cx, cy = px + chunk_size // 2, py + chunk_size // 2
                    pygame.draw.circle(surf, dungeon_color, (cx, cy), max(s(3), chunk_size // 4))

                # Check for hover
                rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
                if chunk_rect.collidepoint(rx, ry):
                    hovered_chunk = (chunk_x, chunk_y, explored)
                    pygame.draw.rect(surf, (255, 255, 255), chunk_rect, s(1))

        # Draw grid if enabled
        if config.map_display.show_grid and chunk_size >= s(8):
            grid_color = (50, 50, 70)
            for dx in range(-visible_chunks_x // 2, visible_chunks_x // 2 + 2):
                x = map_area_x + map_center_x + int((int(center_chunk_x) + dx - center_chunk_x - 0.5) * chunk_size)
                if map_area_x <= x <= map_area_x + map_area_w:
                    pygame.draw.line(surf, grid_color, (x, map_area_y), (x, map_area_y + map_area_h), 1)
            for dy in range(-visible_chunks_y // 2, visible_chunks_y // 2 + 2):
                y = map_area_y + map_center_y + int((int(center_chunk_y) + dy - center_chunk_y - 0.5) * chunk_size)
                if map_area_y <= y <= map_area_y + map_area_h:
                    pygame.draw.line(surf, grid_color, (map_area_x, y), (map_area_x + map_area_w, y), 1)

        # Draw player marker with precise position within chunk
        if config.map_display.show_player_marker:
            # Calculate precise player position within chunk (0.0 to 1.0)
            player_tile_x = character.position.x
            player_tile_y = character.position.y
            player_offset_x = (player_tile_x % Config.CHUNK_SIZE) / Config.CHUNK_SIZE
            player_offset_y = (player_tile_y % Config.CHUNK_SIZE) / Config.CHUNK_SIZE

            # Player position on map with sub-chunk precision
            player_px = map_area_x + map_center_x + int((player_chunk_x - center_chunk_x + player_offset_x) * chunk_size)
            player_py = map_area_y + map_center_y + int((player_chunk_y - center_chunk_y + player_offset_y) * chunk_size)

            # Only draw if in visible area
            if map_area_x <= player_px <= map_area_x + map_area_w and map_area_y <= player_py <= map_area_y + map_area_h:
                marker_size = config.player_marker.size
                marker_color = config.player_marker.color
                # Draw triangle pointing up
                points = [
                    (player_px, player_py - s(marker_size)),
                    (player_px - s(marker_size // 2), player_py + s(marker_size // 2)),
                    (player_px + s(marker_size // 2), player_py + s(marker_size // 2))
                ]
                pygame.draw.polygon(surf, marker_color, points)
                pygame.draw.polygon(surf, (0, 0, 0), points, s(1))

        # Draw waypoint markers and collect rects
        waypoint_rects = []
        if config.map_display.show_waypoint_markers:
            for wp in map_system.get_all_waypoints():
                wp_chunk_x, wp_chunk_y = wp.chunk_coords
                wp_px = map_area_x + map_center_x + int((wp_chunk_x - center_chunk_x) * chunk_size) + chunk_size // 2
                wp_py = map_area_y + map_center_y + int((wp_chunk_y - center_chunk_y) * chunk_size) + chunk_size // 2

                if map_area_x <= wp_px <= map_area_x + map_area_w and map_area_y <= wp_py <= map_area_y + map_area_h:
                    marker_size = config.waypoint_marker.size
                    marker_color = config.waypoint_marker.color
                    # Draw diamond
                    points = [
                        (wp_px, wp_py - s(marker_size)),
                        (wp_px + s(marker_size), wp_py),
                        (wp_px, wp_py + s(marker_size)),
                        (wp_px - s(marker_size), wp_py)
                    ]
                    pygame.draw.polygon(surf, marker_color, points)
                    pygame.draw.polygon(surf, (0, 0, 0), points, s(1))

        # Draw hovered chunk info
        if hovered_chunk and config.map_display.show_coordinates:
            cx, cy, explored = hovered_chunk
            info_y = map_area_y + map_area_h + s(5)
            coord_text = f"Chunk: ({cx}, {cy})"
            if explored:
                type_name = explored.chunk_type.replace('_', ' ').title()
                coord_text += f" - {type_name}"
                if explored.has_dungeon:
                    coord_text += " [DUNGEON]"
            else:
                coord_text += " - Unexplored"
            surf.blit(self.small_font.render(coord_text, True, (200, 200, 200)), (map_area_x, info_y))

        # ========== WAYPOINT PANEL ==========
        panel_x = ww - waypoint_panel_w - s(10)
        panel_y = map_area_y
        panel_h = map_area_h

        # Panel background
        panel_rect = pygame.Rect(panel_x, panel_y, waypoint_panel_w, panel_h)
        pygame.draw.rect(surf, (25, 25, 35), panel_rect)
        pygame.draw.rect(surf, tuple(config.ui.border_color), panel_rect, s(2))

        # Panel title
        surf.blit(self.small_font.render("WAYPOINTS", True, (255, 215, 0)), (panel_x + s(10), panel_y + s(10)))

        # Available slots info
        available_slots = map_system.get_available_slots(character.leveling.level)
        next_unlock = map_system.get_next_unlocked_level(character.leveling.level)
        slots_text = f"Slots: {len(map_system.get_all_waypoints())}/{available_slots}"
        surf.blit(self.tiny_font.render(slots_text, True, (150, 150, 180)), (panel_x + s(10), panel_y + s(30)))
        if next_unlock:
            unlock_text = f"Next at Lv.{next_unlock}"
            surf.blit(self.tiny_font.render(unlock_text, True, (100, 150, 200)), (panel_x + s(10), panel_y + s(45)))

        # Waypoint list
        wp_y = panel_y + s(65)
        wp_list_rects = []
        action_rects = []  # [(screen_rect, slot, action_type), ...]
        btn_size = s(18)

        for i in range(available_slots):
            wp = map_system.get_waypoint(i)
            wp_rect = pygame.Rect(panel_x + s(5), wp_y, waypoint_panel_w - s(10), s(45))

            # Check if hovered
            rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
            is_hovered = wp_rect.collidepoint(rx, ry)

            if wp:
                # Check if this waypoint is being renamed or pending delete
                is_renaming = rename_state is not None and rename_state[0] == i
                is_deleting = delete_confirm_slot == i

                # Filled slot
                if is_deleting:
                    bg_color = (80, 30, 30)  # Red tint for delete confirmation
                elif is_renaming:
                    bg_color = (70, 70, 40)  # Yellow tint for rename mode
                elif is_hovered:
                    bg_color = (50, 50, 70)
                else:
                    bg_color = (35, 35, 50)
                pygame.draw.rect(surf, bg_color, wp_rect)
                if is_deleting:
                    border_color = (255, 100, 100)
                elif is_renaming:
                    border_color = (200, 180, 80)
                else:
                    border_color = (80, 80, 100)
                pygame.draw.rect(surf, border_color, wp_rect, s(2) if (is_renaming or is_deleting) else s(1))

                if is_deleting:
                    # Show delete confirmation
                    confirm_text = f"Delete '{wp.name[:12]}'?"
                    surf.blit(self.small_font.render(confirm_text, True, (255, 200, 200)), (wp_rect.x + s(5), wp_rect.y + s(5)))
                    surf.blit(self.tiny_font.render("Enter=Confirm | Esc=Cancel", True, (255, 150, 150)),
                             (wp_rect.x + s(5), wp_rect.y + s(25)))
                elif is_renaming:
                    # Show text input field
                    input_rect = pygame.Rect(wp_rect.x + s(3), wp_rect.y + s(3), wp_rect.w - s(6), s(20))
                    pygame.draw.rect(surf, (40, 40, 30), input_rect)
                    pygame.draw.rect(surf, (200, 180, 80), input_rect, s(1))

                    # Show current rename text with cursor
                    rename_text = rename_state[1]
                    cursor_blink = (pygame.time.get_ticks() // 500) % 2 == 0
                    display_text = rename_text + ("|" if cursor_blink else "")
                    surf.blit(self.small_font.render(display_text[:20], True, (255, 255, 200)),
                             (input_rect.x + s(3), input_rect.y + s(2)))

                    # Instructions below
                    surf.blit(self.tiny_font.render("Enter=Save | Esc=Cancel", True, (180, 160, 80)),
                             (wp_rect.x + s(5), wp_rect.y + s(28)))
                else:
                    # Waypoint name (truncate to make room for buttons)
                    name_color = (255, 215, 0) if wp.is_spawn else (200, 200, 220)
                    max_name_len = 12 if not wp.is_spawn else 15
                    display_name = wp.name[:max_name_len] + ('...' if len(wp.name) > max_name_len else '')
                    surf.blit(self.small_font.render(display_name, True, name_color), (wp_rect.x + s(5), wp_rect.y + s(5)))

                    # Coordinates
                    pos_text = f"({int(wp.position.x)}, {int(wp.position.y)})"
                    surf.blit(self.tiny_font.render(pos_text, True, (120, 120, 150)), (wp_rect.x + s(5), wp_rect.y + s(25)))

                    # Action buttons (only for non-spawn waypoints)
                    if not wp.is_spawn:
                        # Rename button
                        rename_btn_rect = pygame.Rect(wp_rect.x + wp_rect.w - btn_size * 2 - s(8), wp_rect.y + s(5), btn_size, btn_size)
                        rename_hovered = rename_btn_rect.collidepoint(rx, ry)
                        btn_color = (80, 100, 150) if rename_hovered else (50, 70, 100)
                        pygame.draw.rect(surf, btn_color, rename_btn_rect)
                        pygame.draw.rect(surf, (100, 120, 170), rename_btn_rect, 1)
                        # Draw pencil icon (simple "R")
                        surf.blit(self.tiny_font.render("R", True, (200, 200, 255)), (rename_btn_rect.x + s(5), rename_btn_rect.y + s(2)))
                        action_rects.append((pygame.Rect(wx + rename_btn_rect.x, wy + rename_btn_rect.y, btn_size, btn_size), i, 'rename'))

                        # Delete button
                        delete_btn_rect = pygame.Rect(wp_rect.x + wp_rect.w - btn_size - s(4), wp_rect.y + s(5), btn_size, btn_size)
                        delete_hovered = delete_btn_rect.collidepoint(rx, ry)
                        btn_color = (150, 60, 60) if delete_hovered else (100, 50, 50)
                        pygame.draw.rect(surf, btn_color, delete_btn_rect)
                        pygame.draw.rect(surf, (170, 80, 80), delete_btn_rect, 1)
                        # Draw X
                        surf.blit(self.tiny_font.render("X", True, (255, 150, 150)), (delete_btn_rect.x + s(5), delete_btn_rect.y + s(2)))
                        action_rects.append((pygame.Rect(wx + delete_btn_rect.x, wy + delete_btn_rect.y, btn_size, btn_size), i, 'delete'))

                wp_list_rects.append((pygame.Rect(wx + wp_rect.x, wy + wp_rect.y, wp_rect.w, wp_rect.h), i))
            else:
                # Empty slot
                pygame.draw.rect(surf, (30, 30, 40), wp_rect)
                pygame.draw.rect(surf, (60, 60, 70), wp_rect, s(1))
                surf.blit(self.tiny_font.render(f"Empty Slot {i + 1}", True, (80, 80, 100)), (wp_rect.x + s(5), wp_rect.y + s(15)))

            wp_y += s(50)

        # Instructions at bottom of panel
        instr_text = "Click waypoint to teleport"
        surf.blit(self.tiny_font.render(instr_text, True, (120, 120, 150)), (panel_x + s(10), panel_y + panel_h - s(60)))

        # Teleport cooldown (use game_time for consistency)
        cooldown = map_system.get_teleport_cooldown_remaining(game_time)
        if cooldown > 0:
            cd_text = f"Teleport: {int(cooldown)}s"
            cd_color = (255, 100, 100)
            # Draw cooldown bar
            bar_x = panel_x + s(10)
            bar_y = panel_y + panel_h - s(30)
            bar_w = waypoint_panel_w - s(20)
            bar_h = s(8)
            pygame.draw.rect(surf, (60, 30, 30), (bar_x, bar_y, bar_w, bar_h))
            cooldown_pct = cooldown / config.waypoint.teleport_cooldown
            pygame.draw.rect(surf, (200, 60, 60), (bar_x, bar_y, int(bar_w * cooldown_pct), bar_h))
            pygame.draw.rect(surf, (100, 50, 50), (bar_x, bar_y, bar_w, bar_h), 1)
        else:
            cd_text = "Teleport: Ready"
            cd_color = (100, 255, 100)
        surf.blit(self.tiny_font.render(cd_text, True, cd_color), (panel_x + s(10), panel_y + panel_h - s(45)))

        # Draw to screen
        self.screen.blit(surf, (wx, wy))
        window_rect = pygame.Rect(wx, wy, ww, wh)

        # Map area rect for dragging (map_rect is local, convert to screen)
        map_area_screen_rect = pygame.Rect(wx + map_area_x, wy + map_area_y, map_area_w, map_area_h)

        return window_rect, map_area_screen_rect, wp_list_rects, action_rects

    def render_npc_dialogue_ui(self, npc: NPC, dialogue_lines: List[str], available_quests: List[str],
                               quest_to_turn_in: Optional[str], mouse_pos: Tuple[int, int]):
        """Render NPC dialogue UI with quest options"""
        s = Config.scale
        # Window dimensions
        ww, wh = Config.MENU_MEDIUM_W, Config.MENU_MEDIUM_H
        wx = max(0, (Config.VIEWPORT_WIDTH - ww) // 2)  # Clamp to prevent off-screen
        wy = max(0, (Config.VIEWPORT_HEIGHT - wh) // 2)

        # Create dialogue surface
        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))
        pygame.draw.rect(surf, (100, 100, 120), surf.get_rect(), s(3))

        # NPC name header
        header_bg = pygame.Rect(0, 0, ww, s(50))
        pygame.draw.rect(surf, (40, 40, 60), header_bg)
        pygame.draw.rect(surf, (100, 100, 120), header_bg, s(2))

        name_surf = self.font.render(npc.npc_def.name, True, (255, 215, 0))
        surf.blit(name_surf, (ww // 2 - name_surf.get_width() // 2, s(15)))

        # Close hint
        close_surf = self.tiny_font.render("[F or ESC] Close", True, (180, 180, 200))
        surf.blit(close_surf, (ww - close_surf.get_width() - s(10), s(20)))

        # Dialogue text
        y = s(70)
        for line in dialogue_lines:
            line_surf = self.small_font.render(line, True, (220, 220, 240))
            surf.blit(line_surf, (s(30), y))
            y += s(25)

        y += s(20)

        # Quest section
        button_rects = []

        # Turn in quest (highest priority)
        if quest_to_turn_in:
            npc_db = NPCDatabase.get_instance()
            if quest_to_turn_in in npc_db.quests:
                quest_def = npc_db.quests[quest_to_turn_in]

                # Quest title
                quest_title_surf = self.small_font.render(f"✅ Quest Complete: {quest_def.title}", True, (100, 255, 100))
                surf.blit(quest_title_surf, (s(30), y))
                y += s(30)

                # Turn in button
                button_rect = pygame.Rect(s(30), y, ww - s(60), s(40))
                rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
                is_hovered = button_rect.collidepoint(rx, ry)

                button_color = (60, 120, 60) if is_hovered else (40, 100, 40)
                pygame.draw.rect(surf, button_color, button_rect)
                pygame.draw.rect(surf, (100, 200, 100), button_rect, s(2))

                button_text = self.small_font.render("Turn In Quest", True, (255, 255, 255))
                surf.blit(button_text, (button_rect.centerx - button_text.get_width() // 2, button_rect.y + s(12)))

                button_rects.append(('turn_in', quest_to_turn_in, pygame.Rect(wx + button_rect.x, wy + button_rect.y, button_rect.width, button_rect.height)))
                y += s(50)

        # Available quests
        if available_quests:
            quest_header_surf = self.small_font.render("📜 Available Quests:", True, (200, 200, 255))
            surf.blit(quest_header_surf, (s(30), y))
            y += s(30)

            npc_db = NPCDatabase.get_instance()
            for quest_id in available_quests[:3]:  # Show up to 3 quests
                if quest_id in npc_db.quests:
                    quest_def = npc_db.quests[quest_id]

                    # Quest button
                    button_rect = pygame.Rect(s(30), y, ww - s(60), s(60))
                    rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
                    is_hovered = button_rect.collidepoint(rx, ry)

                    button_color = (60, 80, 120) if is_hovered else (40, 60, 100)
                    pygame.draw.rect(surf, button_color, button_rect)
                    pygame.draw.rect(surf, (100, 150, 200), button_rect, s(2))

                    # Quest icon
                    quest_icon_path = f"quests/{quest_id}.png"
                    image_cache = ImageCache.get_instance()
                    quest_icon = image_cache.get_image(quest_icon_path, (s(40), s(40)))

                    if quest_icon:
                        # Render icon on left side of button
                        surf.blit(quest_icon, (button_rect.x + s(10), button_rect.y + s(10)))
                        title_x = button_rect.x + s(60)
                    else:
                        title_x = button_rect.x + s(10)

                    # Quest title
                    title_surf = self.small_font.render(quest_def.title, True, (220, 220, 255))
                    surf.blit(title_surf, (title_x, button_rect.y + s(8)))

                    # Quest description (truncated)
                    desc = quest_def.description[:60] + "..." if len(quest_def.description) > 60 else quest_def.description
                    desc_surf = self.tiny_font.render(desc, True, (180, 180, 200))
                    surf.blit(desc_surf, (title_x, button_rect.y + s(30)))

                    button_rects.append(('accept', quest_id, pygame.Rect(wx + button_rect.x, wy + button_rect.y, button_rect.width, button_rect.height)))
                    y += s(70)

        # If no quests
        if not quest_to_turn_in and not available_quests:
            no_quest_surf = self.small_font.render("No quests available at this time.", True, (150, 150, 150))
            surf.blit(no_quest_surf, (s(30), y))

        self.screen.blit(surf, (wx, wy))
        window_rect = pygame.Rect(wx, wy, ww, wh)
        return window_rect, button_rects

    def _render_guide_content(self, surf, content_rect, character):
        """Render game guide content"""
        s = Config.scale
        lines = character.encyclopedia.get_game_guide_text()

        # Apply scroll offset
        scroll_offset = character.encyclopedia.scroll_offset
        y = content_rect.y + s(20) - scroll_offset
        x = content_rect.x + s(20)

        for line in lines:
            # Stop if entirely below visible area
            if y > content_rect.bottom:
                break

            # Only render if within visible area
            if line.startswith("==="):
                if y >= content_rect.y - s(30) and y < content_rect.bottom:
                    surf.blit(self.font.render(line, True, (255, 215, 0)), (x, y))
                y += s(30)
            elif line.startswith("•"):
                if y >= content_rect.y - s(20) and y < content_rect.bottom:
                    surf.blit(self.small_font.render(line, True, (200, 200, 220)), (x, y))
                y += s(20)
            elif line == "":
                y += s(10)
            elif line.endswith(":"):
                if y >= content_rect.y - s(25) and y < content_rect.bottom:
                    surf.blit(self.small_font.render(line, True, (150, 200, 255)), (x, y))
                y += s(25)
            else:
                if y >= content_rect.y - s(18) and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(line, True, (180, 180, 200)), (x, y))
                y += s(18)

    def _render_quests_content(self, surf, content_rect, character):
        """Render quest tracking and status content"""
        s = Config.scale
        npc_db = NPCDatabase.get_instance()
        if not npc_db.loaded:
            return

        # Apply scroll offset
        scroll_offset = character.encyclopedia.scroll_offset
        y = content_rect.y + s(15) - scroll_offset
        x = content_rect.x + s(15)

        # Header
        if y >= content_rect.y and y < content_rect.bottom:
            surf.blit(self.font.render("QUEST LOG", True, (255, 215, 0)), (x, y))
        y += s(35)

        # Active Quests Section
        if y >= content_rect.y and y < content_rect.bottom:
            surf.blit(self.small_font.render("ACTIVE QUESTS:", True, (150, 200, 255)), (x, y))
        y += s(25)

        if character.quests.active_quests:
            for quest_id, quest in character.quests.active_quests.items():
                # Quest Title with Icon
                if y >= content_rect.y - s(30) and y < content_rect.bottom:
                    # Try to load quest icon
                    quest_icon_path = f"quests/{quest_id}.png"
                    image_cache = ImageCache.get_instance()
                    quest_icon = image_cache.get_image(quest_icon_path, (s(20), s(20)))

                    if quest_icon:
                        # Render icon
                        surf.blit(quest_icon, (x + s(10), y))
                        # Title next to icon
                        title_text = quest.quest_def.title
                        surf.blit(self.small_font.render(title_text, True, (220, 220, 255)), (x + s(35), y))
                    else:
                        # Fallback: emoji + title
                        title_text = f"📜 {quest.quest_def.title}"
                        surf.blit(self.small_font.render(title_text, True, (220, 220, 255)), (x + s(10), y))
                y += s(25)

                # Quest Description
                if y >= content_rect.y - s(20) and y < content_rect.bottom:
                    desc_text = quest.quest_def.description[:80] + "..." if len(quest.quest_def.description) > 80 else quest.quest_def.description
                    surf.blit(self.tiny_font.render(desc_text, True, (180, 180, 200)), (x + s(20), y))
                y += s(20)

                # Quest Objectives
                if quest.quest_def.objectives.objective_type == "gather":
                    if y >= content_rect.y - s(20) and y < content_rect.bottom:
                        surf.blit(self.tiny_font.render("Objectives:", True, (200, 200, 220)), (x + s(20), y))
                    y += s(18)

                    for item_req in quest.quest_def.objectives.items:
                        item_id = item_req["item_id"]
                        required_qty = item_req["quantity"]
                        current_qty = character.inventory.get_item_count(item_id)

                        # Calculate progress since quest acceptance (using baseline)
                        baseline_qty = quest.baseline_inventory.get(item_id, 0)
                        gathered_since_start = current_qty - baseline_qty

                        # Get item name
                        mat_db = MaterialDatabase.get_instance()
                        item_def = mat_db.get_material(item_id)
                        item_name = item_def.name if item_def else item_id

                        # Progress indicator (compare gathered since start vs required)
                        is_complete = gathered_since_start >= required_qty
                        status_color = (100, 255, 100) if is_complete else (255, 255, 100)
                        check_mark = "✓" if is_complete else "○"

                        if y >= content_rect.y - s(18) and y < content_rect.bottom:
                            obj_text = f"  {check_mark} Gather {item_name}: {gathered_since_start}/{required_qty}"
                            surf.blit(self.tiny_font.render(obj_text, True, status_color), (x + s(30), y))
                        y += s(18)

                elif quest.quest_def.objectives.objective_type == "combat":
                    required_kills = quest.quest_def.objectives.enemies_killed
                    current_kills = character.activities.get_count('combat')

                    # Calculate kills since quest acceptance (using baseline)
                    kills_since_start = current_kills - quest.baseline_combat_kills

                    is_complete = kills_since_start >= required_kills
                    status_color = (100, 255, 100) if is_complete else (255, 255, 100)
                    check_mark = "✓" if is_complete else "○"

                    if y >= content_rect.y - s(20) and y < content_rect.bottom:
                        surf.blit(self.tiny_font.render("Objectives:", True, (200, 200, 220)), (x + s(20), y))
                    y += s(18)

                    if y >= content_rect.y - s(18) and y < content_rect.bottom:
                        obj_text = f"  {check_mark} Defeat enemies: {kills_since_start}/{required_kills}"
                        surf.blit(self.tiny_font.render(obj_text, True, status_color), (x + s(30), y))
                    y += s(18)

                # Quest completion status
                can_complete = quest.check_completion(character)
                if can_complete:
                    if y >= content_rect.y - s(20) and y < content_rect.bottom:
                        surf.blit(self.tiny_font.render("✅ Ready to turn in!", True, (100, 255, 100)), (x + s(20), y))
                    y += s(20)

                # Rewards preview
                if y >= content_rect.y - s(18) and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render("Rewards:", True, (200, 200, 220)), (x + s(20), y))
                y += s(18)

                rewards_parts = []
                if quest.quest_def.rewards.experience > 0:
                    rewards_parts.append(f"{quest.quest_def.rewards.experience} XP")
                if quest.quest_def.rewards.gold > 0:
                    rewards_parts.append(f"{quest.quest_def.rewards.gold} Gold")
                if quest.quest_def.rewards.stat_points > 0:
                    rewards_parts.append(f"{quest.quest_def.rewards.stat_points} Stat Points")
                if quest.quest_def.rewards.skills:
                    rewards_parts.append(f"Skills: {', '.join(quest.quest_def.rewards.skills)}")
                if quest.quest_def.rewards.items:
                    item_names = []
                    for item_req in quest.quest_def.rewards.items:
                        qty = item_req.get("quantity", 1)
                        item_id = item_req.get("item_id", "")
                        mat_db = MaterialDatabase.get_instance()
                        item_def = mat_db.get_material(item_id)
                        item_name = item_def.name if item_def else item_id
                        item_names.append(f"{qty}x {item_name}")
                    if item_names:
                        rewards_parts.append(f"Items: {', '.join(item_names)}")

                for reward_text in rewards_parts:
                    if y >= content_rect.y - s(16) and y < content_rect.bottom:
                        surf.blit(self.tiny_font.render(f"  • {reward_text}", True, (180, 180, 200)), (x + s(30), y))
                    y += s(16)

                y += s(15)  # Space between quests

        else:
            if y >= content_rect.y and y < content_rect.bottom:
                surf.blit(self.small_font.render("No active quests", True, (150, 150, 150)), (x + s(10), y))
            y += s(30)

        y += s(20)

        # Completed Quests Section
        if y >= content_rect.y and y < content_rect.bottom:
            surf.blit(self.small_font.render("COMPLETED QUESTS:", True, (150, 200, 255)), (x, y))
        y += s(25)

        if character.quests.completed_quests:
            for quest_id in character.quests.completed_quests:
                if quest_id in npc_db.quests:
                    quest_def = npc_db.quests[quest_id]
                    if y >= content_rect.y - s(20) and y < content_rect.bottom:
                        # Try to load quest icon
                        quest_icon_path = f"quests/{quest_id}.png"
                        image_cache = ImageCache.get_instance()
                        quest_icon = image_cache.get_image(quest_icon_path, (s(16), s(16)))

                        if quest_icon:
                            # Render icon (greyed out for completed)
                            greyed_icon = quest_icon.copy()
                            greyed_icon.set_alpha(128)
                            surf.blit(greyed_icon, (x + s(10), y))
                            completed_text = f"✓ {quest_def.title}"
                            surf.blit(self.tiny_font.render(completed_text, True, (100, 255, 100)), (x + s(30), y))
                        else:
                            # Fallback without icon
                            completed_text = f"✓ {quest_def.title}"
                            surf.blit(self.tiny_font.render(completed_text, True, (100, 255, 100)), (x + s(10), y))
                    y += s(20)
        else:
            if y >= content_rect.y and y < content_rect.bottom:
                surf.blit(self.small_font.render("No completed quests yet", True, (150, 150, 150)), (x + s(10), y))
            y += s(30)

    def _render_skills_content(self, surf, content_rect, character):
        """Render skills reference content"""
        s = Config.scale
        skill_db = SkillDatabase.get_instance()
        if not skill_db.loaded:
            return

        # Apply scroll offset
        scroll_offset = character.encyclopedia.scroll_offset
        y = content_rect.y + s(15) - scroll_offset
        x = content_rect.x + s(15)

        # Header
        if y >= content_rect.y and y < content_rect.bottom:
            surf.blit(self.small_font.render(f"All Skills ({len(skill_db.skills)} total)", True, (150, 200, 255)), (x, y))
        y += s(30)

        # Group skills by tier
        skills_by_tier = {}
        for skill_id, skill_def in skill_db.skills.items():
            tier = skill_def.tier
            if tier not in skills_by_tier:
                skills_by_tier[tier] = []
            skills_by_tier[tier].append((skill_id, skill_def))

        # Render each tier
        for tier in sorted(skills_by_tier.keys()):
            # Tier header
            tier_colors = {1: (150, 150, 150), 2: (100, 200, 100), 3: (200, 100, 200), 4: (255, 200, 50)}
            if y >= content_rect.y and y < content_rect.bottom:
                surf.blit(self.small_font.render(f"━━ TIER {tier} ━━", True, tier_colors.get(tier, (150, 150, 150))), (x, y))
            y += s(25)

            for skill_id, skill_def in skills_by_tier[tier]:
                # Skip if entirely above visible area
                if y + s(52) < content_rect.y:
                    y += s(52)
                    continue
                # Stop if entirely below visible area
                if y > content_rect.bottom:
                    break

                # Check if player knows this skill
                has_skill = skill_id in character.skills.known_skills
                can_learn = not has_skill and character.skills.can_learn_skill(skill_id, character)[0]

                # Skill icon (if available)
                icon_offset = s(10)
                if skill_def.icon_path and y >= content_rect.y - s(24) and y < content_rect.bottom:
                    image_cache = ImageCache.get_instance()
                    icon = image_cache.get_image(skill_def.icon_path, (s(24), s(24)))
                    if icon:
                        surf.blit(icon, (x + s(10), y))
                        icon_offset = s(40)

                # Skill name
                name_color = (100, 255, 100) if has_skill else ((200, 200, 100) if can_learn else (150, 150, 150))
                status_text = " [KNOWN]" if has_skill else (" [AVAILABLE]" if can_learn else "")
                if y >= content_rect.y and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(f"{skill_def.name}{status_text}", True, name_color), (x + icon_offset, y + s(4)))
                y += s(16)

                # Requirements
                req_text = f"Requires: Lvl {skill_def.requirements.character_level}"
                if skill_def.requirements.stats:
                    stat_reqs = ", ".join(f"{k} {v}" for k, v in skill_def.requirements.stats.items())
                    req_text += f", {stat_reqs}"
                if y >= content_rect.y and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(req_text, True, (120, 120, 140)), (x + icon_offset, y))
                y += s(16)

                # Effect description
                effect_desc = f"{skill_def.effect.effect_type.capitalize()} - {skill_def.effect.category} ({skill_def.effect.magnitude})"
                if y >= content_rect.y and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(effect_desc, True, (100, 150, 200)), (x + icon_offset, y))
                y += s(20)

            y += s(10)

    def _render_titles_content(self, surf, content_rect, character):
        """Render titles reference content"""
        s = Config.scale
        title_db = TitleDatabase.get_instance()
        if not title_db.loaded:
            return

        # Apply scroll offset
        scroll_offset = character.encyclopedia.scroll_offset
        y = content_rect.y + s(15) - scroll_offset
        x = content_rect.x + s(15)

        # Header
        if y >= content_rect.y and y < content_rect.bottom:
            surf.blit(self.small_font.render(f"All Titles ({len(title_db.titles)} total)", True, (255, 215, 0)), (x, y))
        y += s(30)

        # Group titles by tier
        titles_by_tier = {}
        for title_id, title_def in title_db.titles.items():
            tier = title_def.tier
            if tier not in titles_by_tier:
                titles_by_tier[tier] = []
            titles_by_tier[tier].append((title_id, title_def))

        # Tier order
        tier_order = ['novice', 'apprentice', 'journeyman', 'expert', 'master']
        tier_colors = {
            'novice': (150, 150, 150),
            'apprentice': (100, 200, 100),
            'journeyman': (100, 150, 255),
            'expert': (200, 100, 255),
            'master': (255, 200, 50)
        }

        for tier_name in tier_order:
            if tier_name not in titles_by_tier:
                continue

            # Tier header
            if y >= content_rect.y and y < content_rect.bottom:
                surf.blit(self.small_font.render(f"━━ {tier_name.upper()} ━━", True, tier_colors.get(tier_name, (150, 150, 150))), (x, y))
            y += s(25)

            for title_id, title_def in titles_by_tier[tier_name]:
                # Skip if entirely above visible area
                if y + s(52) < content_rect.y:
                    y += s(52)
                    continue
                # Stop if entirely below visible area
                if y > content_rect.bottom:
                    break

                # Check if player has this title
                has_title = character.titles.has_title(title_id)
                name_color = (255, 215, 0) if has_title else (150, 150, 150)
                status_text = " [EARNED]" if has_title else ""

                # Title icon (if available)
                icon_offset = s(10)
                if title_def.icon_path and y >= content_rect.y - s(24) and y < content_rect.bottom:
                    image_cache = ImageCache.get_instance()
                    icon = image_cache.get_image(title_def.icon_path, (s(24), s(24)))
                    if icon:
                        surf.blit(icon, (x + s(10), y))
                        icon_offset = s(40)

                # Title name
                if y >= content_rect.y and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(f"{title_def.name}{status_text}", True, name_color), (x + icon_offset, y + s(4)))
                y += s(16)

                # Requirement
                activity_names = {
                    'mining': 'Ores Mined',
                    'forestry': 'Trees Chopped',
                    'smithing': 'Items Smithed',
                    'refining': 'Materials Refined',
                    'alchemy': 'Potions Brewed',
                    'enchanting': 'Items Enchanted',
                    'engineering': 'Devices Created',
                    'combat': 'Enemies Defeated'
                }
                activity_name = activity_names.get(title_def.activity_type, title_def.activity_type.capitalize())
                req_text = f"Requires: {title_def.acquisition_threshold} {activity_name}"
                if title_def.acquisition_method == "random_drop":
                    tier_chances = {'apprentice': '20%', 'journeyman': '10%', 'expert': '5%', 'master': '2%'}
                    chance = tier_chances.get(tier_name, '?%')
                    req_text += f" ({chance} chance)"
                if y >= content_rect.y and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(req_text, True, (120, 120, 140)), (x + icon_offset, y))
                y += s(16)

                # Bonus
                if y >= content_rect.y and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(f"{title_def.bonus_description}", True, (100, 200, 100)), (x + icon_offset, y))
                y += s(20)

            y += s(10)

    def _render_stats_content(self, surf, content_rect, character):
        """Render comprehensive stat tracking data"""
        s = Config.scale

        if not hasattr(character, 'stat_tracker'):
            # No stat tracker available
            x = content_rect.x + content_rect.width // 2
            y = content_rect.y + content_rect.height // 2
            surf.blit(self.small_font.render("Stat tracking not available", True, (150, 150, 150)),
                     (x - s(100), y))
            return

        # Get all stats from stat tracker
        stats_data = character.stat_tracker.to_dict()

        # Flatten nested dictionaries into (category, stat_name, value) tuples
        flat_stats = []

        def flatten_dict(data, prefix="", category=""):
            """Recursively flatten nested dictionaries"""
            for key, value in data.items():
                # Skip metadata fields
                if key in ["version", "session_start_time"]:
                    continue

                full_key = f"{prefix}.{key}" if prefix else key

                if isinstance(value, dict):
                    # Recursive for nested dicts
                    new_category = key if not category else category
                    flatten_dict(value, full_key, new_category)
                elif isinstance(value, (int, float)) and key not in ["session_start_time"]:
                    # Format stat name nicely
                    display_name = key.replace('_', ' ').title()
                    if prefix:
                        display_name = f"{prefix.split('.')[-1].replace('_', ' ').title()}: {display_name}"

                    flat_stats.append((category or "General", display_name, value))

        flatten_dict(stats_data)

        # Sort by value (descending), then alphabetically by name
        flat_stats.sort(key=lambda x: (-x[2] if isinstance(x[2], (int, float)) else 0, x[1]))

        # Apply scroll offset
        scroll_offset = character.encyclopedia.scroll_offset
        y = content_rect.y + s(15) - scroll_offset
        x = content_rect.x + s(15)

        # Header
        if y >= content_rect.y and y < content_rect.bottom:
            header_text = f"Player Statistics ({len(flat_stats)} tracked)"
            surf.blit(self.small_font.render(header_text, True, (255, 215, 0)), (x, y))
        y += s(30)

        # Session info
        if "total_playtime_seconds" in stats_data:
            playtime_hours = stats_data["total_playtime_seconds"] / 3600.0
            if y >= content_rect.y and y < content_rect.bottom:
                surf.blit(self.tiny_font.render(f"Total Playtime: {playtime_hours:.1f} hours", True, (180, 180, 200)), (x, y))
            y += s(20)

        # Render stats grouped by category
        current_category = None
        for category, stat_name, value in flat_stats:
            # Skip if entirely above visible area (optimization)
            if y + s(18) < content_rect.y:
                y += s(18)
                continue
            # Stop if entirely below visible area
            if y > content_rect.bottom:
                break

            # Category header
            if category != current_category:
                current_category = category
                y += s(10)
                if y >= content_rect.y and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(f"━━ {category.upper()} ━━", True, (120, 150, 200)), (x, y))
                y += s(20)

            # Stat entry
            if y >= content_rect.y and y < content_rect.bottom:
                # Format value nicely
                if isinstance(value, float):
                    if value >= 1000:
                        value_str = f"{value:,.1f}"
                    elif value >= 100:
                        value_str = f"{value:.1f}"
                    else:
                        value_str = f"{value:.2f}"
                elif isinstance(value, int):
                    if value >= 1000:
                        value_str = f"{value:,}"
                    else:
                        value_str = str(value)
                else:
                    value_str = str(value)

                # Color based on value magnitude
                if isinstance(value, (int, float)):
                    if value == 0:
                        color = (100, 100, 100)
                    elif value < 10:
                        color = (150, 150, 150)
                    elif value < 100:
                        color = (180, 180, 200)
                    elif value < 1000:
                        color = (200, 200, 220)
                    else:
                        color = (220, 220, 255)
                else:
                    color = (180, 180, 200)

                # Render stat name and value
                stat_text = f"{stat_name}: {value_str}"
                surf.blit(self.tiny_font.render(stat_text, True, color), (x + s(10), y))

            y += s(18)

    def _render_recipes_content(self, surf, content_rect, character):
        """Render invented recipes content with rich metadata display"""
        s = Config.scale

        # Get invented recipes from character
        invented_recipes = getattr(character, 'invented_recipes', None)
        lines = character.encyclopedia.get_invented_recipes_text(invented_recipes)

        # Apply scroll offset
        scroll_offset = character.encyclopedia.scroll_offset
        y = content_rect.y + s(20) - scroll_offset
        x = content_rect.x + s(20)

        # Colors for different line types
        COLORS = {
            'header': (255, 215, 0),      # Golden for main headers
            'discipline': (100, 180, 255), # Blue for discipline headers
            'count': (150, 255, 150),     # Light green for counts
            'tier1': (180, 180, 180),     # Gray - Common
            'tier2': (100, 255, 100),     # Green - Uncommon
            'tier3': (100, 150, 255),     # Blue - Rare
            'tier4': (200, 100, 255),     # Purple - Epic
            'type': (180, 180, 200),      # Light gray for type info
            'stat': (255, 220, 150),      # Warm yellow for stats
            'tags': (150, 200, 255),      # Light blue for tags
            'applies': (100, 220, 200),   # Cyan for enchantment targets
            'effect': (255, 180, 100),    # Orange for effects
            'recipe': (200, 180, 150),    # Tan for recipe materials
            'lore': (150, 150, 170),      # Gray for narrative
            'default': (180, 180, 200),   # Default text color
        }

        for line in lines:
            # Stop if entirely below visible area
            if y > content_rect.bottom:
                break

            # Determine style based on line content
            if line.startswith("==="):
                # Main header - golden
                if y >= content_rect.y - s(30) and y < content_rect.bottom:
                    surf.blit(self.font.render(line, True, COLORS['header']), (x, y))
                y += s(30)

            elif line.startswith("---"):
                # Discipline header - blue
                if y >= content_rect.y - s(25) and y < content_rect.bottom:
                    surf.blit(self.small_font.render(line, True, COLORS['discipline']), (x, y))
                y += s(25)

            elif line.startswith("Total Inventions:"):
                # Count line - light green
                if y >= content_rect.y - s(20) and y < content_rect.bottom:
                    surf.blit(self.small_font.render(line, True, COLORS['count']), (x, y))
                y += s(20)

            elif line.startswith("  [T"):
                # Recipe entry - tier + name (main item header)
                if y >= content_rect.y - s(22) and y < content_rect.bottom:
                    # Color by tier
                    if "[T1]" in line:
                        color = COLORS['tier1']
                    elif "[T2]" in line:
                        color = COLORS['tier2']
                    elif "[T3]" in line:
                        color = COLORS['tier3']
                    elif "[T4]" in line:
                        color = COLORS['tier4']
                    else:
                        color = COLORS['default']
                    surf.blit(self.small_font.render(line, True, color), (x, y))
                y += s(22)

            elif line.startswith("@type"):
                # Type info - light gray, indented
                if y >= content_rect.y - s(16) and y < content_rect.bottom:
                    display_text = "    " + line[12:]  # Remove @type prefix
                    surf.blit(self.tiny_font.render(display_text, True, COLORS['type']), (x, y))
                y += s(16)

            elif line.startswith("@stat"):
                # Stat info - warm yellow, indented
                if y >= content_rect.y - s(16) and y < content_rect.bottom:
                    display_text = "    " + line[12:]  # Remove @stat prefix
                    surf.blit(self.tiny_font.render(display_text, True, COLORS['stat']), (x, y))
                y += s(16)

            elif line.startswith("@tags"):
                # Tags - light blue, indented
                if y >= content_rect.y - s(16) and y < content_rect.bottom:
                    display_text = "    Tags: " + line[12:]  # Remove @tags prefix
                    surf.blit(self.tiny_font.render(display_text, True, COLORS['tags']), (x, y))
                y += s(16)

            elif line.startswith("@applies"):
                # Enchantment applicability - cyan, indented
                if y >= content_rect.y - s(16) and y < content_rect.bottom:
                    display_text = "    Applies to: " + line[12:]  # Remove @applies prefix
                    surf.blit(self.tiny_font.render(display_text, True, COLORS['applies']), (x, y))
                y += s(16)

            elif line.startswith("@effect"):
                # Enchantment effect - orange, indented
                if y >= content_rect.y - s(16) and y < content_rect.bottom:
                    display_text = "    Effect: " + line[12:]  # Remove @effect prefix
                    surf.blit(self.tiny_font.render(display_text, True, COLORS['effect']), (x, y))
                y += s(16)

            elif line.startswith("@recipe"):
                # Recipe materials - tan, indented
                if y >= content_rect.y - s(16) and y < content_rect.bottom:
                    display_text = "    Materials: " + line[12:]  # Remove @recipe prefix
                    surf.blit(self.tiny_font.render(display_text, True, COLORS['recipe']), (x, y))
                y += s(16)

            elif line.startswith("@lore"):
                # Narrative/lore - italic-style gray, indented
                if y >= content_rect.y - s(16) and y < content_rect.bottom:
                    display_text = "    " + line[12:]  # Remove @lore prefix
                    surf.blit(self.tiny_font.render(display_text, True, COLORS['lore']), (x, y))
                y += s(16)

            elif line == "":
                y += s(8)

            else:
                # Default text
                if y >= content_rect.y - s(18) and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(line, True, COLORS['default']), (x, y))
                y += s(18)

    def render_notifications(self, notifications: List[Notification]):
        y = 50
        for notification in notifications:
            alpha = int(255 * min(1.0, notification.lifetime / 3.0))
            surf = self.font.render(notification.message, True, notification.color)
            surf.set_alpha(alpha)
            x = Config.VIEWPORT_WIDTH // 2 - surf.get_width() // 2

            bg = pygame.Surface((surf.get_width() + 20, surf.get_height() + 10), pygame.SRCALPHA)
            bg.fill((0, 0, 0, int(180 * alpha / 255)))
            self.screen.blit(bg, (x - 10, y - 5))

            self.screen.blit(surf, (x, y))
            y += surf.get_height() + 15

    def render_debug_messages(self):
        """Render on-screen debug messages (max 5, bottom-left corner)."""
        from core.debug_display import get_debug_manager

        manager = get_debug_manager()
        if not manager.is_enabled():
            return

        messages = manager.get_messages()
        if not messages:
            return

        # Position in bottom-left corner, above inventory panel
        x = 10
        y = Config.VIEWPORT_HEIGHT - 120  # Above inventory panel

        # Render each message with semi-transparent background
        for i, message in enumerate(messages):
            # Use small font for compact display
            surf = self.small_font.render(message, True, (200, 200, 255))

            # Background for readability
            bg = pygame.Surface((surf.get_width() + 10, surf.get_height() + 4), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 150))
            self.screen.blit(bg, (x, y - (i * 22)))

            # Text
            self.screen.blit(surf, (x + 5, y + 2 - (i * 22)))

    def render_inventory_panel(self, character: Character, mouse_pos: Tuple[int, int]):
        panel_rect = pygame.Rect(Config.INVENTORY_PANEL_X, Config.INVENTORY_PANEL_Y,
                                 Config.INVENTORY_PANEL_WIDTH, Config.INVENTORY_PANEL_HEIGHT)
        pygame.draw.rect(self.screen, Config.COLOR_UI_BG, panel_rect)
        self.render_text("INVENTORY", 20, Config.INVENTORY_PANEL_Y + 10, bold=True)

        # Render weight bar
        weight_bar_x = 120
        weight_bar_y = Config.INVENTORY_PANEL_Y + 12
        weight_bar_width = 120
        weight_bar_height = 12

        current_weight = character.get_total_weight()
        max_capacity = character.get_max_carry_capacity()
        weight_ratio = current_weight / max_capacity if max_capacity > 0 else 1.0

        # Color based on encumbrance (green until over, then red)
        if weight_ratio <= 1.0:
            bar_color = (80, 180, 80)  # Green
        else:
            # Red intensity based on how far over (cap at 50% over for visual)
            over_amount = min(0.5, weight_ratio - 1.0)
            red_intensity = int(150 + over_amount * 200)
            bar_color = (min(255, red_intensity), 80, 80)

        # Background
        pygame.draw.rect(self.screen, (40, 40, 40), (weight_bar_x, weight_bar_y, weight_bar_width, weight_bar_height))
        # Fill (cap visual at bar width)
        fill_width = min(weight_bar_width, int(weight_bar_width * weight_ratio))
        pygame.draw.rect(self.screen, bar_color, (weight_bar_x, weight_bar_y, fill_width, weight_bar_height))
        # Border
        pygame.draw.rect(self.screen, (100, 100, 100), (weight_bar_x, weight_bar_y, weight_bar_width, weight_bar_height), 1)
        # Weight text
        weight_text = f"{current_weight:.1f}/{max_capacity:.1f}"
        weight_surf = self.tiny_font.render(weight_text, True, (255, 255, 255))
        self.screen.blit(weight_surf, (weight_bar_x + weight_bar_width + 5, weight_bar_y))

        # Render equipped tools section
        tools_y = Config.INVENTORY_PANEL_Y + 35
        self.render_text("Equipped Tools:", 20, tools_y, small=True)
        tools_y += 20

        slot_size = 50
        spacing = 10

        # Render axe slot
        axe_x = 20
        axe_rect = pygame.Rect(axe_x, tools_y, slot_size, slot_size)
        equipped_axe = character.equipment.slots.get('axe')
        axe_hovered = axe_rect.collidepoint(mouse_pos)

        # Highlight if hovered
        slot_color = Config.COLOR_SLOT_FILLED if equipped_axe else Config.COLOR_SLOT_EMPTY
        if axe_hovered and equipped_axe:
            slot_color = (80, 100, 120)  # Highlight color
        pygame.draw.rect(self.screen, slot_color, axe_rect)
        pygame.draw.rect(self.screen, Config.COLOR_EQUIPPED if equipped_axe else Config.COLOR_SLOT_BORDER, axe_rect, 2)

        # Set tooltip if hovered over equipped axe
        if axe_hovered and equipped_axe:
            self.pending_tool_tooltip = (equipped_axe, 'axe', mouse_pos, character)

        if equipped_axe:
            # Try to display axe icon
            from rendering.image_cache import ImageCache
            icon_displayed = False
            if hasattr(equipped_axe, 'item_id') and equipped_axe.item_id:
                icon_path = f"tools/{equipped_axe.item_id}.png"  # ImageCache adds items/ prefix
                image_cache = ImageCache.get_instance()
                icon = image_cache.get_image(icon_path, (slot_size - 10, slot_size - 10))
                if icon:
                    self.screen.blit(icon, (axe_x + 5, tools_y + 5))
                    icon_displayed = True

            # Fallback to text if no icon
            if not icon_displayed:
                tier_surf = self.tiny_font.render(f"T{equipped_axe.tier}", True, (255, 255, 255))
                self.screen.blit(tier_surf, (axe_x + 5, tools_y + 5))
                name_surf = self.tiny_font.render("Axe", True, (255, 255, 255))
                self.screen.blit(name_surf, (axe_x + 5, tools_y + slot_size - 15))
        else:
            # Show empty slot label
            label_surf = self.tiny_font.render("Axe", True, (100, 100, 100))
            self.screen.blit(label_surf, (axe_x + 10, tools_y + 18))

        # Render pickaxe slot
        pick_x = axe_x + slot_size + spacing
        pick_rect = pygame.Rect(pick_x, tools_y, slot_size, slot_size)
        equipped_pick = character.equipment.slots.get('pickaxe')
        pick_hovered = pick_rect.collidepoint(mouse_pos)

        # Highlight if hovered
        slot_color = Config.COLOR_SLOT_FILLED if equipped_pick else Config.COLOR_SLOT_EMPTY
        if pick_hovered and equipped_pick:
            slot_color = (80, 100, 120)  # Highlight color
        pygame.draw.rect(self.screen, slot_color, pick_rect)
        pygame.draw.rect(self.screen, Config.COLOR_EQUIPPED if equipped_pick else Config.COLOR_SLOT_BORDER, pick_rect, 2)

        # Set tooltip if hovered over equipped pickaxe
        if pick_hovered and equipped_pick:
            self.pending_tool_tooltip = (equipped_pick, 'pickaxe', mouse_pos, character)

        if equipped_pick:
            # Try to display pickaxe icon
            from rendering.image_cache import ImageCache
            icon_displayed = False
            if hasattr(equipped_pick, 'item_id') and equipped_pick.item_id:
                icon_path = f"tools/{equipped_pick.item_id}.png"  # ImageCache adds items/ prefix
                image_cache = ImageCache.get_instance()
                icon = image_cache.get_image(icon_path, (slot_size - 10, slot_size - 10))
                if icon:
                    self.screen.blit(icon, (pick_x + 5, tools_y + 5))
                    icon_displayed = True

            # Fallback to text if no icon
            if not icon_displayed:
                tier_surf = self.tiny_font.render(f"T{equipped_pick.tier}", True, (255, 255, 255))
                self.screen.blit(tier_surf, (pick_x + 5, tools_y + 5))
                name_surf = self.tiny_font.render("Pick", True, (255, 255, 255))
                self.screen.blit(name_surf, (pick_x + 5, tools_y + slot_size - 15))
        else:
            # Show empty slot label
            label_surf = self.tiny_font.render("Pick", True, (100, 100, 100))
            self.screen.blit(label_surf, (pick_x + 8, tools_y + 18))

        start_x, start_y = 20, tools_y + slot_size + 20
        slot_size = Config.INVENTORY_SLOT_SIZE
        spacing = 10  # Increased from 5 to 10 for better icon visibility
        slots_per_row = Config.INVENTORY_SLOTS_PER_ROW
        hovered_slot = None

        for i, item_stack in enumerate(character.inventory.slots):
            row, col = i // slots_per_row, i % slots_per_row
            x, y = start_x + col * (slot_size + spacing), start_y + row * (slot_size + spacing)
            slot_rect = pygame.Rect(x, y, slot_size, slot_size)
            is_hovered = slot_rect.collidepoint(mouse_pos)

            if is_hovered and item_stack:
                hovered_slot = (i, item_stack, slot_rect)

            # Check if THIS SPECIFIC item instance is equipped (not just any item with same ID)
            is_equipped = False
            if item_stack and item_stack.is_equipment():
                equipment = item_stack.get_equipment()
                if equipment:
                    # Check if this specific equipment instance is in any slot
                    for slot_item in character.equipment.slots.values():
                        if slot_item is equipment:  # Object identity check
                            is_equipped = True
                            break

            pygame.draw.rect(self.screen, Config.COLOR_SLOT_FILLED if item_stack else Config.COLOR_SLOT_EMPTY,
                             slot_rect)

            # Special border for equipped items
            if is_equipped:
                border = Config.COLOR_EQUIPPED
                border_width = 3
            elif is_hovered:
                border = Config.COLOR_SLOT_SELECTED
                border_width = 2
            else:
                border = Config.COLOR_SLOT_BORDER
                border_width = 2
            pygame.draw.rect(self.screen, border, slot_rect, border_width)

            if item_stack and i != character.inventory.dragging_slot:
                self.render_item_in_slot(item_stack, slot_rect, is_equipped)

        if character.inventory.dragging_stack:
            drag_rect = pygame.Rect(mouse_pos[0] - slot_size // 2, mouse_pos[1] - slot_size // 2, slot_size, slot_size)
            pygame.draw.rect(self.screen, Config.COLOR_SLOT_FILLED, drag_rect)
            pygame.draw.rect(self.screen, Config.COLOR_SLOT_SELECTED, drag_rect, 3)
            self.render_item_in_slot(character.inventory.dragging_stack, drag_rect, False)

        if hovered_slot and not character.inventory.dragging_stack:
            _, item_stack, _ = hovered_slot
            # Defer tooltip rendering to ensure it appears on top of all UI elements
            self.pending_tooltip = (item_stack, mouse_pos, character, False)  # False = not from equipment UI

    def render_item_in_slot(self, item_stack: ItemStack, rect: pygame.Rect, is_equipped: bool = False):
        """
        Render an item in an inventory slot with optional image support.
        Falls back to colored rectangles if no image is available.
        """
        image_cache = ImageCache.get_instance()
        # Increased padding from 5 to 8 for better icon visibility
        inner = pygame.Rect(rect.x + 8, rect.y + 8, rect.width - 16, rect.height - 16)

        # Determine item properties
        icon_path = None
        name = ""
        tier = 1
        rarity = "common"

        if item_stack.is_equipment():
            equipment = item_stack.get_equipment()
            if equipment:
                icon_path = equipment.icon_path
                name = equipment.name
                tier = equipment.tier
                rarity = equipment.rarity
        else:
            mat = item_stack.get_material()
            if mat:
                icon_path = mat.icon_path
                name = mat.name
                tier = mat.tier
                rarity = mat.rarity

        # Try to load image from cache
        image = image_cache.get_image(icon_path, (inner.width, inner.height)) if icon_path else None

        if image:
            # Render image
            self.screen.blit(image, inner.topleft)
        else:
            # Fallback: Render colored rectangle
            color = Config.RARITY_COLORS.get(rarity, (200, 200, 200))
            pygame.draw.rect(self.screen, color, inner)

        # Overlay text elements (always shown)
        # Show "E" for equipped items OR tier for unequipped
        if is_equipped:
            e_surf = self.font.render("E", True, (255, 255, 255))
            e_rect = e_surf.get_rect(center=inner.center)
            # Black outline
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
                self.screen.blit(self.font.render("E", True, (0, 0, 0)), (e_rect.x + dx, e_rect.y + dy))
            self.screen.blit(e_surf, e_rect)
        else:
            # Show tier in top-left
            tier_surf = self.small_font.render(f"T{tier}", True, (255, 255, 255))
            tier_rect = tier_surf.get_rect(topleft=(rect.x + 4, rect.y + 4))
            # Black outline
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.screen.blit(self.small_font.render(f"T{tier}", True, (0, 0, 0)),
                                (tier_rect.x + dx, tier_rect.y + dy))
            self.screen.blit(tier_surf, tier_rect)

        # Show item name at bottom
        if name:
            name_surf = self.tiny_font.render(name[:8], True, (255, 255, 255))
            name_rect = name_surf.get_rect(centerx=rect.centerx, bottom=rect.bottom - 2)
            # Black outline for readability
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.screen.blit(self.tiny_font.render(name[:8], True, (0, 0, 0)),
                                 (name_rect.x + dx, name_rect.y + dy))
            self.screen.blit(name_surf, name_rect)

        # Show quantity for stackable items
        if item_stack.quantity > 1:
            qty_text = str(item_stack.quantity)
            qty_surf = self.small_font.render(qty_text, True, (255, 255, 255))
            qty_rect = qty_surf.get_rect(bottomright=(rect.right - 3, rect.bottom - 3))
            # Black outline
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.screen.blit(self.small_font.render(qty_text, True, (0, 0, 0)),
                                 (qty_rect.x + dx, qty_rect.y + dy))
            self.screen.blit(qty_surf, qty_rect)

    def render_item_tooltip(self, item_stack: ItemStack, mouse_pos: Tuple[int, int], character: Character):
        # Check if equipment
        if item_stack.is_equipment():
            equipment = item_stack.get_equipment()
            if equipment:
                # Use crafted_stats from ItemStack if available, otherwise use equipment.bonuses
                # This ensures unequipped items still show their crafted bonuses
                display_stats = item_stack.crafted_stats if item_stack.crafted_stats else equipment.bonuses
                self.render_equipment_tooltip(equipment, mouse_pos, character, from_inventory=True,
                                              crafted_stats=display_stats)
                return

        # Regular material tooltip
        mat = item_stack.get_material()
        if not mat:
            return

        # Calculate height based on whether we have crafted_stats to display
        base_height = 120
        stats_height = 0
        if item_stack.crafted_stats:
            stats_height = 25 + (len(item_stack.crafted_stats) * 18)  # Header + stats lines

        tw, th, pad = 250, base_height + stats_height, 10
        x, y = mouse_pos[0] + 15, mouse_pos[1] + 15
        if x + tw > Config.SCREEN_WIDTH:
            x = mouse_pos[0] - tw - 15
        if y + th > Config.SCREEN_HEIGHT:
            y = mouse_pos[1] - th - 15

        surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        surf.fill(Config.COLOR_TOOLTIP_BG)

        y_pos = pad
        # Use actual item_stack rarity, not material definition rarity
        actual_rarity = item_stack.rarity
        color = Config.RARITY_COLORS.get(actual_rarity, (200, 200, 200))
        surf.blit(self.font.render(mat.name, True, color), (pad, y_pos))
        y_pos += 25
        surf.blit(self.small_font.render(f"Tier {mat.tier} | {mat.category.capitalize()}", True, (180, 180, 180)),
                  (pad, y_pos))
        y_pos += 20
        surf.blit(self.small_font.render(f"Rarity: {actual_rarity.capitalize()}", True, color), (pad, y_pos))
        y_pos += 20

        # Display crafted stats if present
        if item_stack.crafted_stats:
            y_pos += 5
            surf.blit(self.small_font.render("Crafted Bonuses:", True, (100, 255, 100)), (pad, y_pos))
            y_pos += 18
            for stat_name, stat_value in item_stack.crafted_stats.items():
                # Format stat name nicely (capitalize and add spaces)
                display_name = stat_name.replace('_', ' ').title()
                # Format value with + if positive
                if isinstance(stat_value, (int, float)):
                    value_str = f"+{stat_value}" if stat_value >= 0 else str(stat_value)
                else:
                    value_str = str(stat_value)
                stat_text = f"  {display_name}: {value_str}"
                surf.blit(self.tiny_font.render(stat_text, True, (150, 220, 150)), (pad, y_pos))
                y_pos += 16

        self.screen.blit(surf, (x, y))

    def _group_recipes_by_type(self, recipes, equip_db, mat_db):
        """Group recipes by their output type for organized display - station-specific grouping"""
        from collections import defaultdict

        if not recipes:
            return []

        # Detect station type from first recipe
        station_type = recipes[0].station_type if recipes else 'smithing'

        grouped = defaultdict(list)

        for recipe in recipes:
            output_type = 'Other'

            # Check if this is an invented recipe (player-created via INVENT)
            if hasattr(recipe, 'metadata') and recipe.metadata.get('invented', False):
                output_type = 'Invented Recipes'
            # Handle enchanting recipes separately (they don't have materials)
            elif station_type == 'adornments' and hasattr(recipe, 'is_enchantment') and recipe.is_enchantment:
                # Enchanting: Just use 'Enchantments' category - we'll sort alphabetically
                output_type = 'Enchantments'
            elif equip_db.is_equipment(recipe.output_id):
                # Equipment items
                equip = equip_db.create_equipment_from_id(recipe.output_id)
                if equip:
                    if equip.item_type == 'weapon':
                        output_type = 'Weapons'
                    elif equip.item_type == 'shield':
                        output_type = 'Weapons'
                    elif equip.item_type == 'armor':
                        output_type = 'Armor'
                    elif equip.item_type == 'tool':
                        output_type = 'Tools'
                    elif equip.item_type == 'accessory':
                        output_type = 'Accessories'
            else:
                # Material items
                mat = mat_db.get_material(recipe.output_id)
                if mat:
                    # Station-specific grouping
                    if station_type == 'engineering':
                        # Engineering: Group by device type
                        if hasattr(mat, 'item_type'):
                            if mat.item_type == 'turret':
                                output_type = 'Turrets'
                            elif mat.item_type == 'trap':
                                output_type = 'Traps'
                            elif mat.item_type == 'bomb':
                                output_type = 'Bombs'
                            elif mat.item_type == 'utility':
                                output_type = 'Utility Devices'
                        if output_type == 'Other' and mat.category == 'station':
                            output_type = 'Crafting Stations'
                        elif output_type == 'Other':
                            output_type = 'Other Devices'

                    elif station_type == 'alchemy':
                        # Alchemy: Group potions by subtype/effect
                        if 'health' in mat.name.lower() or (hasattr(mat, 'effect') and 'healing' in mat.effect.lower()):
                            output_type = 'Health Potions'
                        elif 'mana' in mat.name.lower() or (hasattr(mat, 'effect') and 'mana' in mat.effect.lower()):
                            output_type = 'Mana Potions'
                        elif hasattr(mat, 'effect') and ('strength' in mat.effect.lower() or 'damage' in mat.effect.lower()):
                            output_type = 'Combat Buffs'
                        elif hasattr(mat, 'effect') and ('speed' in mat.effect.lower() or 'agility' in mat.effect.lower()):
                            output_type = 'Movement Buffs'
                        elif mat.category == 'consumable':
                            output_type = 'Other Potions'
                        else:
                            output_type = 'Other Materials'

                    elif station_type == 'refining':
                        # Refining: Group by material category
                        if mat.category == 'metal':
                            output_type = 'Metals & Ingots'
                        elif mat.category == 'ore':
                            output_type = 'Processed Ores'
                        elif mat.category == 'elemental':
                            output_type = 'Elemental Materials'
                        elif mat.category in ['wood', 'stone']:
                            output_type = 'Refined Resources'
                        else:
                            output_type = 'Other Materials'

                    else:
                        # Smithing or default: Group by tier
                        if hasattr(mat, 'tier'):
                            if mat.tier == 1:
                                output_type = 'Tier 1'
                            elif mat.tier == 2:
                                output_type = 'Tier 2'
                            elif mat.tier == 3:
                                output_type = 'Tier 3'
                            elif mat.tier >= 4:
                                output_type = 'Tier 4+'
                        if output_type == 'Other' and mat.category == 'station':
                            output_type = 'Stations'
                        # If still 'Other', keep it as 'Other'

            grouped[output_type].append(recipe)

        # Define order based on station type (Invented Recipes always appear first)
        if station_type == 'engineering':
            type_order = ['Invented Recipes', 'Turrets', 'Traps', 'Bombs', 'Utility Devices', 'Crafting Stations', 'Other Devices', 'Other']
        elif station_type == 'alchemy':
            type_order = ['Invented Recipes', 'Health Potions', 'Mana Potions', 'Combat Buffs', 'Movement Buffs', 'Other Potions', 'Other Materials', 'Other']
        elif station_type == 'refining':
            type_order = ['Invented Recipes', 'Metals & Ingots', 'Processed Ores', 'Elemental Materials', 'Refined Resources', 'Other Materials', 'Other']
        elif station_type == 'adornments':
            type_order = ['Invented Recipes', 'Enchantments', 'Other']
        else:
            # Smithing and default
            type_order = ['Invented Recipes', 'Weapons', 'Armor', 'Tools', 'Accessories', 'Tier 1', 'Tier 2', 'Tier 3', 'Tier 4+', 'Stations', 'Other']

        # Return as ordered list of tuples
        result = []
        for type_name in type_order:
            if type_name in grouped and grouped[type_name]:
                recipes_list = grouped[type_name]
                # Sort enchantments alphabetically by name
                if station_type == 'adornments' and type_name == 'Enchantments':
                    recipes_list = sorted(recipes_list, key=lambda r: getattr(r, 'enchantment_name', '').lower())
                result.append((type_name, recipes_list))

        return result

    def render_crafting_ui(self, character: Character, mouse_pos: Tuple[int, int], selected_recipe=None, user_placement=None, minigame_active=False):
        """
        Render crafting UI with two-panel layout:
        - Left panel (450px): Recipe list
        - Right panel (700px): Placement visualization + craft buttons

        Args:
            selected_recipe: Currently selected recipe (to highlight in UI)
            user_placement: User's current material placement (Dict[str, str])
            minigame_active: Whether a minigame is currently active (hides craft buttons)
        """
        if user_placement is None:
            user_placement = {}
        if not character.crafting_ui_open or not character.active_station:
            return None

        # Store these temporarily so child methods can access them
        # (Python scoping doesn't allow nested functions to see parameters)
        self._temp_selected_recipe = selected_recipe
        self._temp_user_placement = user_placement
        self._temp_minigame_active = minigame_active

        # Initialize tooltip tracking for this frame
        self._pending_tooltips = []

        # Always render recipe list on the left (pass scroll offset from game engine)
        # Note: Renderer doesn't have direct access to game engine, so we need to get it via a hack
        # Check if there's a scroll offset to use (this will be set by the caller)
        scroll_offset = getattr(self, '_temp_scroll_offset', 0)
        recipe_result = self._render_recipe_selection_sidebar(character, mouse_pos, scroll_offset)

        # Render any pending tooltips (after main surface is blitted)
        if self._pending_tooltips:
            # Show first tooltip only (avoid clutter)
            self.render_tooltip(self._pending_tooltips[0], mouse_pos)

        # If a recipe is selected, render placement UI on the right
        # (Note: Placement UI rendering is handled by the recipe selection sidebar)

        return recipe_result

    def _render_recipe_selection_sidebar(self, character: Character, mouse_pos: Tuple[int, int], scroll_offset: int = 0):
        """Render recipe selection sidebar - left side with scrolling support"""
        recipe_db = RecipeDatabase.get_instance()
        mat_db = MaterialDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()

        s = Config.scale  # Shorthand for readability
        # Window dimensions - expanded to fit two panels
        ww, wh = Config.MENU_LARGE_W, Config.MENU_MEDIUM_H
        left_panel_w = s(450)
        right_panel_w = s(500)  # Reduced to fit in LARGE menu
        separator_x = left_panel_w + s(20)

        wx = max(0, (Config.VIEWPORT_WIDTH - ww) // 2)  # Clamp to prevent off-screen
        wy = max(0, (Config.VIEWPORT_HEIGHT - wh) // 2)

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 240))

        # Header
        header = f"{character.active_station.station_type.value.upper()} (T{character.active_station.tier})"
        surf.blit(self.font.render(header, True, character.active_station.get_color()), (s(20), s(20)))

        # Interactive Mode button (top-right of header)
        interactive_btn_w, interactive_btn_h = s(140), s(32)
        interactive_btn_x = ww - interactive_btn_w - s(20)
        interactive_btn_y = s(15)
        interactive_btn_rect = pygame.Rect(interactive_btn_x, interactive_btn_y, interactive_btn_w, interactive_btn_h)

        # Button styling
        is_btn_hovered = interactive_btn_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))
        btn_color = (70, 100, 70) if is_btn_hovered else (50, 80, 50)
        pygame.draw.rect(surf, btn_color, interactive_btn_rect, border_radius=s(5))
        pygame.draw.rect(surf, (100, 180, 100), interactive_btn_rect, s(2), border_radius=s(5))

        # Button text
        btn_text = self.small_font.render("Interactive Mode", True, (220, 255, 220))
        text_x = interactive_btn_x + (interactive_btn_w - btn_text.get_width()) // 2
        text_y = interactive_btn_y + (interactive_btn_h - btn_text.get_height()) // 2
        surf.blit(btn_text, (text_x, text_y))

        # Help text (moved down to make room for button)
        surf.blit(self.small_font.render("[ESC] Close | Select recipe to place materials", True, (180, 180, 180)), (s(20), s(48)))

        # Get recipes for this station
        recipes = recipe_db.get_recipes_for_station(character.active_station.station_type.value,
                                                    character.active_station.tier)

        # ======================
        # LEFT PANEL: Recipe List with Scrolling (ORGANIZED BY TYPE)
        # ======================
        visible_recipes = []  # Initialize to empty list
        if not recipes:
            surf.blit(self.font.render("No recipes available", True, (200, 200, 200)), (s(20), s(80)))
        else:
            # Group recipes by type
            grouped_recipes = self._group_recipes_by_type(recipes, equip_db, mat_db)

            # Flatten grouped recipes into a list with headers
            # Format: [('header', 'Weapons'), ('recipe', recipe_obj), ('recipe', recipe_obj), ('header', 'Tools'), ...]
            flat_list = []
            for type_name, type_recipes in grouped_recipes:
                flat_list.append(('header', type_name))
                for recipe in type_recipes:
                    flat_list.append(('recipe', recipe))

            # Apply scroll offset and show items
            total_items = len(flat_list)
            # Calculate max_visible based on available vertical space
            # Window height: 600px, start at y=70, leaves ~530px
            # Average recipe height: ~85px (70px base + spacing)
            # Can fit approximately: 530/85 ≈ 6 recipes, but be generous for small recipes
            # Use 8 as a safe value that won't overflow the window
            max_visible = 999999  # No limit - renderer will stop when out of space
            start_idx = min(scroll_offset, max(0, total_items - 1))
            # Don't cap end_idx here - let rendering loop handle it based on available space
            visible_items = flat_list[start_idx:]  # Start from scroll offset, render until out of space

            # Render items until we run out of vertical space
            y_off = s(70)
            max_y = wh - s(20)  # Leave 20px margin at bottom
            items_rendered = 0

            for i, item in enumerate(visible_items):
                # Check if we have room for this item BEFORE rendering it
                if item[0] == 'header':
                    needed_height = s(28)
                else:  # recipe
                    recipe = item[1]
                    num_inputs = len(recipe.inputs)
                    needed_height = max(s(70), s(35) + num_inputs * s(16) + s(5)) + s(8)

                if y_off + needed_height > max_y:
                    # Out of space, stop rendering
                    break

                items_rendered += 1
                item_type, item_data = item

                if item_type == 'header':
                    # Render type header
                    header_text = item_data
                    header_color = (255, 215, 0)  # Gold
                    header_surf = self.font.render(header_text, True, header_color)
                    surf.blit(header_surf, (s(25), y_off))

                    # Underline
                    underline_y = y_off + s(22)
                    pygame.draw.line(surf, header_color, (s(25), underline_y), (left_panel_w - s(35), underline_y), 1)

                    y_off += s(28)

                elif item_type == 'recipe':
                    recipe = item_data
                    # Compact recipe display (no buttons, just info)
                    num_inputs = len(recipe.inputs)
                    btn_height = max(s(70), s(35) + num_inputs * s(16) + s(5))

                    btn = pygame.Rect(s(20), y_off, left_panel_w - s(30), btn_height)
                    can_craft = recipe_db.can_craft(recipe, character.inventory)

                    # Highlight selected recipe with gold border
                    is_selected = (self._temp_selected_recipe and self._temp_selected_recipe.recipe_id == recipe.recipe_id)

                    btn_color = (60, 80, 60) if can_craft else (80, 60, 60)
                    if is_selected:
                        btn_color = (80, 70, 30)  # Gold tint for selected

                    pygame.draw.rect(surf, btn_color, btn)
                    border_color = (255, 215, 0) if is_selected else (100, 100, 100)
                    border_width = 3 if is_selected else 2
                    pygame.draw.rect(surf, border_color, btn, border_width)

                    # Output name
                    is_equipment = equip_db.is_equipment(recipe.output_id)
                    if is_equipment:
                        equip = equip_db.create_equipment_from_id(recipe.output_id)
                        out_name = equip.name if equip else recipe.output_id
                        color = Config.RARITY_COLORS.get(equip.rarity, (200, 200, 200)) if equip else (200, 200, 200)
                    else:
                        out_mat = mat_db.get_material(recipe.output_id)
                        out_name = out_mat.name if out_mat else recipe.output_id
                        color = Config.RARITY_COLORS.get(out_mat.rarity, (200, 200, 200)) if out_mat else (200, 200, 200)

                    surf.blit(self.font.render(f"{out_name} x{recipe.output_qty}", True, color),
                              (btn.x + s(10), btn.y + s(8)))

                    # Material requirements (compact) with tooltips
                    req_y = btn.y + s(30)
                    for inp in recipe.inputs:
                        mat_id = inp.get('materialId', '')
                        req = inp.get('quantity', 0)
                        avail = character.inventory.get_item_count(mat_id)
                        mat = mat_db.get_material(mat_id)
                        mat_name = mat.name if mat else mat_id
                        req_color = (100, 255, 100) if avail >= req or Config.DEBUG_INFINITE_RESOURCES else (255, 100, 100)

                        # Render material requirement text
                        mat_text = self.small_font.render(f"{mat_name}: {avail}/{req}", True, req_color)
                        surf.blit(mat_text, (btn.x + s(15), req_y))

                        # Check for hover and add tooltip (use relative coordinates)
                        mat_rect = pygame.Rect(btn.x + s(15), req_y, mat_text.get_width(), mat_text.get_height())
                        rel_mouse_x, rel_mouse_y = mouse_pos[0] - wx, mouse_pos[1] - wy
                        if mat_rect.collidepoint(rel_mouse_x, rel_mouse_y):
                            if mat:
                                tooltip_text = f"{mat.name} (Tier {mat.tier}) - Need: {req}, Have: {avail}"
                                if not hasattr(self, '_pending_tooltips'):
                                    self._pending_tooltips = []
                                self._pending_tooltips.append(tooltip_text)

                        req_y += s(16)

                    y_off += btn_height + s(8)

            # Calculate end_idx based on items actually rendered
            end_idx = start_idx + items_rendered

            # Show scroll indicators
            if start_idx > 0 or end_idx < total_items:
                scroll_text = f"Showing {start_idx + 1}-{end_idx} of {total_items}"
                scroll_surf = self.small_font.render(scroll_text, True, (150, 150, 150))
                surf.blit(scroll_surf, (s(20), s(50)))

                # Show scroll arrows
                if start_idx > 0:
                    up_arrow = self.small_font.render("▲ Scroll Up", True, (100, 200, 100))
                    surf.blit(up_arrow, (left_panel_w - s(120), s(50)))
                if end_idx < total_items:
                    down_arrow = self.small_font.render("▼ Scroll Down", True, (100, 200, 100))
                    surf.blit(down_arrow, (left_panel_w - s(120), wh - s(30)))

        # ======================
        # DIVIDER
        # ======================
        pygame.draw.line(surf, (100, 100, 100), (separator_x, s(60)), (separator_x, wh - s(20)), 2)

        # ======================
        # RIGHT PANEL: Placement + Buttons
        # ======================
        right_panel_x = separator_x + s(20)
        right_panel_y = s(70)

        if self._temp_selected_recipe:
            # Selected recipe - show placement and buttons
            selected = self._temp_selected_recipe
            can_craft = recipe_db.can_craft(selected, character.inventory)

            # ======================
            # OUTPUT PREVIEW PANEL
            # ======================
            preview_h = s(100)
            preview_rect = pygame.Rect(right_panel_x, right_panel_y, right_panel_w - s(40), preview_h)
            pygame.draw.rect(surf, (40, 50, 40), preview_rect)
            pygame.draw.rect(surf, (100, 150, 100), preview_rect, 2)

            # Title
            surf.blit(self.small_font.render("OUTPUT PREVIEW", True, (150, 200, 150)), (preview_rect.x + s(10), preview_rect.y + s(8)))

            # Get output item info
            is_equipment = equip_db.is_equipment(selected.output_id)
            if is_equipment:
                output_item = equip_db.create_equipment_from_id(selected.output_id)
                output_name = output_item.name if output_item else selected.output_id
                output_color = Config.RARITY_COLORS.get(output_item.rarity, (200, 200, 200)) if output_item else (200, 200, 200)
                output_icon_path = output_item.icon_path if output_item else None
            else:
                output_item = mat_db.get_material(selected.output_id)
                output_name = output_item.name if output_item else selected.output_id
                output_color = Config.RARITY_COLORS.get(output_item.rarity, (200, 200, 200)) if output_item else (200, 200, 200)
                output_icon_path = output_item.icon_path if output_item else None

            # Draw output icon (large)
            if output_icon_path:
                image_cache = ImageCache.get_instance()
                icon = image_cache.get_image(output_icon_path, (s(70), s(70)))
                if icon:
                    surf.blit(icon, (preview_rect.x + s(15), preview_rect.y + s(25)))

            # Draw output name and quantity
            name_text = f"{output_name}"
            qty_text = f"x{selected.output_qty}"
            surf.blit(self.font.render(name_text, True, output_color), (preview_rect.x + s(95), preview_rect.y + s(35)))
            surf.blit(self.small_font.render(qty_text, True, (200, 200, 200)), (preview_rect.x + s(95), preview_rect.y + s(60)))

            # Tier badge (if equipment)
            if is_equipment and output_item:
                tier_text = f"T{output_item.tier}"
                tier_color = {1: (150, 150, 150), 2: (100, 200, 100), 3: (100, 150, 255), 4: (200, 100, 255), 5: (255, 200, 50)}.get(output_item.tier, (150, 150, 150))
                surf.blit(self.small_font.render(tier_text, True, tier_color), (preview_rect.x + s(95), preview_rect.y + s(78)))

            # Placement visualization area (moved down to make room for preview)
            placement_h = s(270)  # Reduced from 380 to fit preview
            placement_rect = pygame.Rect(right_panel_x, right_panel_y + preview_h + s(10), right_panel_w - s(40), placement_h)
            pygame.draw.rect(surf, (30, 30, 40), placement_rect)
            pygame.draw.rect(surf, (80, 80, 90), placement_rect, 2)

            # Render discipline-specific placement UI
            station_type = character.active_station.station_type.value
            # IMPORTANT: Grid size is determined by STATION tier (physical constraint)
            # Recipe tier is only for display purposes (like tier badge)
            station_tier = character.active_station.tier
            placement_grid_rects = {}  # Will store grid cell rects for click detection

            if station_type == 'smithing':
                # Smithing: Grid-based placement
                placement_grid_rects = self.render_smithing_grid(surf, placement_rect, station_tier, selected, self._temp_user_placement, mouse_pos)
            elif station_type == 'refining':
                # Refining: Hub-and-spoke
                placement_grid_rects = self.render_refining_hub(surf, placement_rect, station_tier, selected, self._temp_user_placement, mouse_pos)
            elif station_type == 'alchemy':
                # Alchemy: Sequential
                placement_grid_rects = self.render_alchemy_sequence(surf, placement_rect, station_tier, selected, self._temp_user_placement, mouse_pos)
            elif station_type == 'engineering':
                # Engineering: Slot-type
                placement_grid_rects = self.render_engineering_slots(surf, placement_rect, station_tier, selected, self._temp_user_placement, mouse_pos)
            elif station_type == 'adornments':
                # Enchanting: Vertex-based pattern renderer
                placement_grid_rects = self.render_adornment_pattern(surf, placement_rect, station_tier, selected, self._temp_user_placement, mouse_pos)

            # Craft buttons at bottom of right panel (hide if minigame active)
            if can_craft and not self._temp_minigame_active:
                btn_y = placement_rect.bottom + s(20)
                instant_btn_w, instant_btn_h = s(120), s(40)
                minigame_btn_w, minigame_btn_h = s(120), s(40)

                # Center the buttons horizontally in right panel
                total_btn_w = instant_btn_w + minigame_btn_w + s(20)
                start_x = right_panel_x + (right_panel_w - s(40) - total_btn_w) // 2

                instant_btn_x = start_x
                minigame_btn_x = start_x + instant_btn_w + s(20)

                # Instant button (gray)
                instant_rect = pygame.Rect(instant_btn_x, btn_y, instant_btn_w, instant_btn_h)
                pygame.draw.rect(surf, (60, 60, 60), instant_rect)
                pygame.draw.rect(surf, (120, 120, 120), instant_rect, 2)
                instant_text = self.font.render("Instant", True, (200, 200, 200))
                surf.blit(instant_text, (instant_btn_x + s(25), btn_y + s(10)))

                instant_subtext = self.small_font.render("0 XP", True, (150, 150, 150))
                surf.blit(instant_subtext, (instant_btn_x + s(40), btn_y + s(28)))

                # Minigame button (gold)
                minigame_rect = pygame.Rect(minigame_btn_x, btn_y, minigame_btn_w, minigame_btn_h)
                pygame.draw.rect(surf, (80, 60, 20), minigame_rect)
                pygame.draw.rect(surf, (255, 215, 0), minigame_rect, 2)
                minigame_text = self.font.render("Minigame", True, (255, 215, 0))
                surf.blit(minigame_text, (minigame_btn_x + s(10), btn_y + s(10)))

                minigame_subtext = self.small_font.render("1.5x XP", True, (255, 200, 100))
                surf.blit(minigame_subtext, (minigame_btn_x + s(30), btn_y + s(28)))
            elif self._temp_minigame_active:
                # Show "Minigame in progress" message
                btn_y = placement_rect.bottom + s(30)
                progress_text = self.font.render("Minigame in Progress...", True, (255, 215, 0))
                surf.blit(progress_text, (right_panel_x + (right_panel_w - s(40) - progress_text.get_width())//2, btn_y))
            else:
                # Can't craft - show why
                btn_y = placement_rect.bottom + s(30)
                cannot_text = self.font.render("Insufficient Materials", True, (255, 100, 100))
                surf.blit(cannot_text, (right_panel_x + (right_panel_w - s(40) - cannot_text.get_width())//2, btn_y))
        else:
            # No recipe selected - show prompt
            prompt_text = self.font.render("← Select a recipe to view details", True, (150, 150, 150))
            surf.blit(prompt_text, (right_panel_x + s(50), right_panel_y + s(150)))

        self.screen.blit(surf, (wx, wy))
        # Return window rect, recipes, and grid cell rects for click handling
        grid_rects_absolute = []
        if self._temp_selected_recipe:
            # Convert relative grid rects to absolute screen coordinates
            for rect, grid_pos in placement_grid_rects:
                abs_rect = rect.move(wx, wy)  # Offset by window position
                grid_rects_absolute.append((abs_rect, grid_pos))
        # Return full recipe list (not just visible) so scroll calculation works
        return_recipes = recipes if recipes else []

        # Convert interactive button rect to absolute coordinates
        interactive_btn_abs = interactive_btn_rect.move(wx, wy)

        return pygame.Rect(wx, wy, ww, wh), return_recipes, grid_rects_absolute, interactive_btn_abs

    def render_interactive_crafting_ui(self, character: Character, interactive_ui, mouse_pos: Tuple[int, int]):
        """
        Render the interactive crafting UI where players manually place materials.

        Args:
            character: Player character
            interactive_ui: InteractiveBaseUI instance (from core.interactive_crafting)
            mouse_pos: Current mouse position

        Returns:
            Dict with click regions for game engine handling:
            {
                'window_rect': pygame.Rect,
                'material_rects': [(rect, item_stack), ...],
                'placement_rects': [(rect, position), ...],
                'button_rects': {'clear': rect, 'instant': rect, 'minigame': rect}
            }
        """
        from core.interactive_crafting import (
            InteractiveSmithingUI, InteractiveRefiningUI, InteractiveAlchemyUI,
            InteractiveEngineeringUI, InteractiveAdornmentsUI
        )

        s = Config.scale
        mat_db = MaterialDatabase.get_instance()
        equip_db = EquipmentDatabase.get_instance()

        # Initialize tooltip tracking
        self._pending_tooltips = []

        # Window dimensions - use LARGE menu for better fit
        ww, wh = Config.MENU_LARGE_W, Config.MENU_LARGE_H
        wx = max(0, (Config.VIEWPORT_WIDTH - ww) // 2)
        wy = max(0, (Config.VIEWPORT_HEIGHT - wh) // 2)

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 240))

        # Header
        station_name = character.active_station.station_type.value.upper()
        tier = character.active_station.tier
        header = f"INTERACTIVE {station_name} (T{tier})"
        surf.blit(self.font.render(header, True, character.active_station.get_color()), (s(20), s(20)))
        surf.blit(self.small_font.render("[ESC] Close", True, (180, 180, 180)), (ww - s(120), s(20)))

        # ==============================================================================
        # LEFT PANEL: Material Palette
        # ==============================================================================
        palette_x = s(20)
        palette_y = s(60)
        palette_w = s(250)  # Reduced from 300
        palette_h = wh - s(80)  # Reduced from 100

        # Background
        palette_rect = pygame.Rect(palette_x, palette_y, palette_w, palette_h)
        pygame.draw.rect(surf, (30, 30, 40), palette_rect)
        pygame.draw.rect(surf, (100, 100, 120), palette_rect, 2)

        # Header
        palette_header = self.small_font.render("MATERIALS (Click to Select)", True, (200, 200, 200))
        surf.blit(palette_header, (palette_x + s(10), palette_y + s(8)))

        # Get available materials
        available_materials = interactive_ui.get_available_materials()

        # Render materials (scrollable list)
        material_rects = []
        item_h = s(45)
        visible_count = int((palette_h - s(40)) / item_h)
        scroll_offset = interactive_ui.material_palette_scroll
        start_idx = min(scroll_offset, max(0, len(available_materials) - visible_count))

        mat_y = palette_y + s(35)
        for i in range(start_idx, min(start_idx + visible_count, len(available_materials))):
            mat_stack = available_materials[i]
            mat_def = mat_db.get_material(mat_stack.item_id)
            if not mat_def:
                continue

            # Item rect
            item_rect = pygame.Rect(palette_x + s(10), mat_y, palette_w - s(20), item_h - s(5))

            # Check if selected
            is_selected = (interactive_ui.selected_material and
                          interactive_ui.selected_material.item_id == mat_stack.item_id)

            # Check if hovered
            is_hovered = item_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))

            # Background color
            if is_selected:
                bg_color = (80, 100, 80)
            elif is_hovered:
                bg_color = (60, 70, 80)
            else:
                bg_color = (40, 45, 55)

            pygame.draw.rect(surf, bg_color, item_rect, border_radius=s(3))

            # Border (tier color)
            tier_colors = {1: (150, 150, 150), 2: (100, 200, 100), 3: (100, 150, 255), 4: (200, 100, 255)}
            border_color = tier_colors.get(mat_def.tier, (100, 100, 100))
            if is_selected:
                border_color = (255, 215, 0)  # Gold for selected
            pygame.draw.rect(surf, border_color, item_rect, s(2), border_radius=s(3))

            # Material PNG icon (left side)
            icon_x = item_rect.x + s(5)
            icon_y = item_rect.y + s(5)
            icon_size = s(32)
            image_cache = ImageCache.get_instance()
            icon = image_cache.get_image(f"materials/{mat_stack.item_id}.png", target_size=(icon_size, icon_size))
            if icon:
                surf.blit(icon, (icon_x, icon_y))

            # Material name (right of icon)
            name_text = self.tiny_font.render(mat_def.name, True, (220, 220, 220))
            surf.blit(name_text, (icon_x + icon_size + s(8), item_rect.y + s(5)))

            # Quantity and tier (right of icon)
            qty_text = self.tiny_font.render(f"x{mat_stack.quantity} (T{mat_def.tier})", True, (180, 180, 180))
            surf.blit(qty_text, (icon_x + icon_size + s(8), item_rect.y + s(22)))

            # Tooltip on hover
            if is_hovered:
                tooltip_text = f"{mat_def.name} (Tier {mat_def.tier}) x{mat_stack.quantity}"
                self._pending_tooltips.append(tooltip_text)

            # Store for click detection
            abs_rect = item_rect.move(wx, wy)
            material_rects.append((abs_rect, mat_stack))

            mat_y += item_h

        # Scroll indicators
        if start_idx > 0:
            scroll_up_text = self.tiny_font.render("▲ Scroll Up (Mouse Wheel)", True, (150, 200, 150))
            surf.blit(scroll_up_text, (palette_x + s(20), palette_y + s(12)))
        if start_idx + visible_count < len(available_materials):
            scroll_down_text = self.tiny_font.render("▼ Scroll Down", True, (150, 200, 150))
            surf.blit(scroll_down_text, (palette_x + s(20), palette_rect.bottom - s(18)))

        # ==============================================================================
        # RIGHT PANEL: Placement Area
        # ==============================================================================
        placement_x = palette_rect.right + s(20)  # Reduced spacing
        placement_y = s(60)
        placement_w = ww - placement_x - s(20)
        placement_h = wh - s(220)  # Leave 220px for bottom buttons and status

        # Background
        placement_rect = pygame.Rect(placement_x, placement_y, placement_w, placement_h)
        pygame.draw.rect(surf, (25, 30, 35), placement_rect)
        pygame.draw.rect(surf, (100, 120, 140), placement_rect, 2)

        # Render discipline-specific placement area
        placement_rects = []

        if isinstance(interactive_ui, InteractiveSmithingUI):
            # GRID-BASED (Smithing only)
            grid_size = interactive_ui.grid_size
            cell_size = min(s(60), (placement_w - s(40)) // grid_size)
            grid_offset_x = placement_x + (placement_w - grid_size * cell_size) // 2
            grid_offset_y = placement_y + s(30)

            # Header
            header_text = f"SMITHING GRID ({grid_size}x{grid_size})"
            surf.blit(self.small_font.render(header_text, True, (200, 200, 200)), (placement_x + s(10), placement_y + s(8)))

            # Render grid
            for y in range(grid_size):
                for x in range(grid_size):
                    cell_x = grid_offset_x + x * cell_size
                    cell_y = grid_offset_y + y * cell_size
                    cell_rect = pygame.Rect(cell_x, cell_y, cell_size - s(2), cell_size - s(2))

                    # Check if cell has material
                    pos = (x, y)
                    placed_mat = interactive_ui.grid.get(pos)

                    # Cell color
                    is_hovered = cell_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))
                    if placed_mat:
                        mat_def = mat_db.get_material(placed_mat.item_id)
                        tier_colors = {1: (60, 60, 70), 2: (60, 80, 60), 3: (60, 70, 90), 4: (90, 60, 90)}
                        cell_color = tier_colors.get(mat_def.tier if mat_def else 1, (50, 50, 60))
                    elif is_hovered:
                        cell_color = (70, 80, 90)
                    else:
                        cell_color = (40, 45, 50)

                    pygame.draw.rect(surf, cell_color, cell_rect, border_radius=s(3))

                    # Border
                    border_color = (120, 140, 160) if is_hovered else (80, 90, 100)
                    pygame.draw.rect(surf, border_color, cell_rect, s(2), border_radius=s(3))

                    # Material icon/text
                    if placed_mat:
                        mat_def = mat_db.get_material(placed_mat.item_id)
                        if mat_def:
                            # Try to show PNG icon
                            icon_size = min(cell_size - s(10), s(40))
                            image_cache = ImageCache.get_instance()
                            icon = image_cache.get_image(f"materials/{placed_mat.item_id}.png", target_size=(icon_size, icon_size))
                            if icon:
                                icon_x = cell_rect.centerx - icon_size // 2
                                icon_y = cell_rect.centery - icon_size // 2
                                surf.blit(icon, (icon_x, icon_y))
                            else:
                                # Fallback to text abbreviation if no icon
                                abbrev = mat_def.name[:3].upper()
                                text = self.tiny_font.render(abbrev, True, (220, 220, 220))
                                text_x = cell_rect.centerx - text.get_width() // 2
                                text_y = cell_rect.centery - text.get_height() // 2
                                surf.blit(text, (text_x, text_y))

                    # Store for click detection
                    abs_rect = cell_rect.move(wx, wy)
                    placement_rects.append((abs_rect, pos))

        elif isinstance(interactive_ui, InteractiveRefiningUI):
            # HUB-AND-SPOKE (Refining) with tier-varying core slots
            num_cores = interactive_ui.num_core_slots
            header_text = f"HUB-AND-SPOKE PLACEMENT ({num_cores} core, {interactive_ui.num_surrounding_slots} surrounding)"
            surf.blit(self.small_font.render(header_text, True, (200, 200, 200)), (placement_x + s(10), placement_y + s(8)))

            # Render core slots (center area)
            core_size = s(70)
            center_x = placement_x + placement_w // 2
            center_y = placement_y + placement_h // 2

            # Layout core slots based on count
            if num_cores == 1:
                core_positions = [(0, 0)]
            elif num_cores == 2:
                core_positions = [(-40, 0), (40, 0)]
            elif num_cores == 3:
                core_positions = [(-50, -30), (50, -30), (0, 40)]
            else:  # More than 3
                # Arrange in a small circle
                import math
                core_positions = []
                for i in range(num_cores):
                    angle = (i / num_cores) * 2 * math.pi - math.pi/2
                    core_positions.append((int(35 * math.cos(angle)), int(35 * math.sin(angle))))

            for core_idx, (offset_x, offset_y) in enumerate(core_positions):
                core_x = center_x + s(offset_x) - core_size // 2
                core_y = center_y + s(offset_y) - core_size // 2
                core_rect = pygame.Rect(core_x, core_y, core_size, core_size)

                # Check if slot has material
                core_mat = interactive_ui.core_slots[core_idx]
                is_hovered = core_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))

                core_color = (80, 100, 80) if core_mat else ((70, 80, 90) if is_hovered else (50, 60, 70))
                pygame.draw.rect(surf, core_color, core_rect, border_radius=s(8))
                pygame.draw.rect(surf, (140, 160, 180) if is_hovered else (100, 120, 140), core_rect, s(3), border_radius=s(8))

                # Core label
                core_label = self.tiny_font.render(f"C{core_idx+1}", True, (200, 200, 200))
                surf.blit(core_label, (core_rect.centerx - core_label.get_width() // 2, core_rect.y + s(5)))

                # Material icon or name
                if core_mat:
                    mat_def = mat_db.get_material(core_mat.item_id)
                    if mat_def:
                        # Try PNG icon
                        icon_size = s(40)
                        image_cache = ImageCache.get_instance()
                        icon = image_cache.get_image(f"materials/{core_mat.item_id}.png", target_size=(icon_size, icon_size))
                        if icon:
                            icon_x = core_rect.centerx - icon_size // 2
                            icon_y = core_rect.centery - icon_size // 2 + s(8)
                            surf.blit(icon, (icon_x, icon_y))

                            # Quantity indicator (if > 1)
                            if core_mat.quantity > 1:
                                qty_text = self.tiny_font.render(f"x{core_mat.quantity}", True, (255, 255, 255))
                                qty_bg = pygame.Rect(icon_x + icon_size - qty_text.get_width() - s(4),
                                                     icon_y + icon_size - s(18),
                                                     qty_text.get_width() + s(6), s(16))
                                pygame.draw.rect(surf, (20, 20, 20, 200), qty_bg, border_radius=s(3))
                                surf.blit(qty_text, (qty_bg.x + s(3), qty_bg.y + s(2)))
                        else:
                            mat_text = self.tiny_font.render(mat_def.name[:6], True, (220, 220, 220))
                            surf.blit(mat_text, (core_rect.centerx - mat_text.get_width() // 2, core_rect.centery + s(5)))

                            # Quantity indicator for text fallback
                            if core_mat.quantity > 1:
                                qty_text = self.tiny_font.render(f"(x{core_mat.quantity})", True, (180, 180, 180))
                                surf.blit(qty_text, (core_rect.centerx - qty_text.get_width() // 2, core_rect.centery + s(20)))

                abs_core_rect = core_rect.move(wx, wy)
                placement_rects.append((abs_core_rect, ('core', core_idx)))

            # Surrounding slots (tier-varying count in circle)
            surrounding_size = s(60)
            radius = s(130)
            num_surrounding = interactive_ui.num_surrounding_slots

            # Generate angles evenly distributed around circle
            import math
            for i in range(num_surrounding):
                angle_rad = (i / num_surrounding) * 2 * math.pi - math.pi/2  # Start at top
                slot_x = center_x + int(radius * math.cos(angle_rad)) - surrounding_size // 2
                slot_y = center_y + int(radius * math.sin(angle_rad)) - surrounding_size // 2
                slot_rect = pygame.Rect(slot_x, slot_y, surrounding_size, surrounding_size)

                # Check if slot has material
                slot_mat = interactive_ui.surrounding_slots[i]
                is_hovered = slot_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))

                slot_color = (70, 90, 70) if slot_mat else ((65, 75, 85) if is_hovered else (45, 55, 65))
                pygame.draw.rect(surf, slot_color, slot_rect, border_radius=s(6))
                pygame.draw.rect(surf, (120, 140, 160) if is_hovered else (90, 110, 130), slot_rect, s(2), border_radius=s(6))

                # Slot number
                num_text = self.tiny_font.render(str(i+1), True, (150, 150, 150))
                surf.blit(num_text, (slot_rect.x + s(5), slot_rect.y + s(5)))

                # Material icon or abbreviation
                if slot_mat:
                    mat_def = mat_db.get_material(slot_mat.item_id)
                    if mat_def:
                        # Try PNG icon
                        icon_size = s(35)
                        image_cache = ImageCache.get_instance()
                        icon = image_cache.get_image(f"materials/{slot_mat.item_id}.png", target_size=(icon_size, icon_size))
                        if icon:
                            icon_x = slot_rect.centerx - icon_size // 2
                            icon_y = slot_rect.centery - icon_size // 2 + s(8)
                            surf.blit(icon, (icon_x, icon_y))

                            # Quantity indicator (if > 1)
                            if slot_mat.quantity > 1:
                                qty_text = self.tiny_font.render(f"x{slot_mat.quantity}", True, (255, 255, 255))
                                qty_bg = pygame.Rect(icon_x + icon_size - qty_text.get_width() - s(4),
                                                     icon_y + icon_size - s(18),
                                                     qty_text.get_width() + s(6), s(16))
                                pygame.draw.rect(surf, (20, 20, 20, 200), qty_bg, border_radius=s(3))
                                surf.blit(qty_text, (qty_bg.x + s(3), qty_bg.y + s(2)))
                        else:
                            abbrev = mat_def.name[:4].upper()
                            mat_text = self.tiny_font.render(abbrev, True, (220, 220, 220))
                            surf.blit(mat_text, (slot_rect.centerx - mat_text.get_width() // 2, slot_rect.centery + s(5)))

                            # Quantity indicator for text fallback
                            if slot_mat.quantity > 1:
                                qty_text = self.tiny_font.render(f"(x{slot_mat.quantity})", True, (180, 180, 180))
                                surf.blit(qty_text, (slot_rect.centerx - qty_text.get_width() // 2, slot_rect.centery + s(18)))

                abs_slot_rect = slot_rect.move(wx, wy)
                placement_rects.append((abs_slot_rect, ('surrounding', i)))

        elif isinstance(interactive_ui, InteractiveAlchemyUI):
            # SEQUENTIAL SLOTS (Alchemy)
            header_text = f"SEQUENTIAL PLACEMENT ({len(interactive_ui.slots)} slots)"
            surf.blit(self.small_font.render(header_text, True, (200, 200, 200)), (placement_x + s(10), placement_y + s(8)))

            # Render slots in a horizontal row
            slot_w = s(100)
            slot_h = s(80)
            spacing = s(15)
            total_width = len(interactive_ui.slots) * slot_w + (len(interactive_ui.slots) - 1) * spacing
            start_x = placement_x + (placement_w - total_width) // 2
            slot_y = placement_y + s(60)

            for i in range(len(interactive_ui.slots)):
                slot_x = start_x + i * (slot_w + spacing)
                slot_rect = pygame.Rect(slot_x, slot_y, slot_w, slot_h)

                # Check if slot has material
                slot_mat = interactive_ui.slots[i]
                is_hovered = slot_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))

                slot_color = (70, 80, 90) if slot_mat else ((60, 70, 80) if is_hovered else (40, 50, 60))
                pygame.draw.rect(surf, slot_color, slot_rect, border_radius=s(5))
                pygame.draw.rect(surf, (120, 140, 160) if is_hovered else (90, 110, 130), slot_rect, s(2), border_radius=s(5))

                # Slot label
                label_text = self.tiny_font.render(f"Slot {i+1}", True, (180, 180, 180))
                surf.blit(label_text, (slot_rect.centerx - label_text.get_width() // 2, slot_rect.y + s(5)))

                # Material icon or name
                if slot_mat:
                    mat_def = mat_db.get_material(slot_mat.item_id)
                    if mat_def:
                        # Try PNG icon
                        icon_size = s(40)
                        image_cache = ImageCache.get_instance()
                        icon = image_cache.get_image(f"materials/{slot_mat.item_id}.png", target_size=(icon_size, icon_size))
                        if icon:
                            icon_x = slot_rect.centerx - icon_size // 2
                            icon_y = slot_rect.centery - icon_size // 2 + s(5)
                            surf.blit(icon, (icon_x, icon_y))

                            # Quantity indicator (if > 1)
                            if slot_mat.quantity > 1:
                                qty_text = self.tiny_font.render(f"x{slot_mat.quantity}", True, (255, 255, 255))
                                qty_bg = pygame.Rect(icon_x + icon_size - qty_text.get_width() - s(4),
                                                     icon_y + icon_size - s(18),
                                                     qty_text.get_width() + s(6), s(16))
                                pygame.draw.rect(surf, (20, 20, 20, 200), qty_bg, border_radius=s(3))
                                surf.blit(qty_text, (qty_bg.x + s(3), qty_bg.y + s(2)))
                        else:
                            mat_text = self.tiny_font.render(mat_def.name[:10], True, (220, 220, 220))
                            surf.blit(mat_text, (slot_rect.centerx - mat_text.get_width() // 2, slot_rect.centery))

                            # Quantity indicator for text fallback
                            if slot_mat.quantity > 1:
                                qty_text = self.tiny_font.render(f"(x{slot_mat.quantity})", True, (180, 180, 180))
                                surf.blit(qty_text, (slot_rect.centerx - qty_text.get_width() // 2, slot_rect.centery + s(15)))

                    # Tooltip on hover
                    if is_hovered and mat_def:
                        tooltip_text = f"{mat_def.name} x{slot_mat.quantity}" if slot_mat.quantity > 1 else mat_def.name
                        # Store for later rendering (after main surface blit)
                        if not hasattr(self, '_pending_tooltips'):
                            self._pending_tooltips = []
                        self._pending_tooltips.append(tooltip_text)

                abs_slot_rect = slot_rect.move(wx, wy)
                placement_rects.append((abs_slot_rect, i))

        elif isinstance(interactive_ui, InteractiveEngineeringUI):
            # SLOT-TYPE GROUPING (Engineering)
            header_text = "COMPONENT PLACEMENT (Slot-Type Canvas)"
            surf.blit(self.small_font.render(header_text, True, (200, 200, 200)), (placement_x + s(10), placement_y + s(8)))

            # Get available slot types for this tier
            slot_types = interactive_ui.available_slot_types
            slot_h = s(60)
            type_y = placement_y + s(40)

            for slot_type in slot_types:
                # Type label
                type_label = self.small_font.render(slot_type.upper(), True, (200, 200, 200))
                surf.blit(type_label, (placement_x + s(15), type_y + s(5)))

                # Render materials in this type
                materials = interactive_ui.slots.get(slot_type, [])
                slot_x = placement_x + s(150)

                for i, mat in enumerate(materials):
                    mat_def = mat_db.get_material(mat.item_id)
                    if mat_def:
                        # Material chip
                        chip_w = s(120)
                        chip_h = s(35)
                        chip_rect = pygame.Rect(slot_x + i * (chip_w + s(10)), type_y, chip_w, chip_h)

                        is_hovered = chip_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))
                        chip_color = (70, 90, 70) if not is_hovered else (85, 105, 85)
                        pygame.draw.rect(surf, chip_color, chip_rect, border_radius=s(4))
                        pygame.draw.rect(surf, (120, 160, 120), chip_rect, s(2), border_radius=s(4))

                        # Material name
                        mat_text = self.tiny_font.render(mat_def.name[:12], True, (220, 220, 220))
                        surf.blit(mat_text, (chip_rect.x + s(5), chip_rect.centery - mat_text.get_height() // 2))

                        # Quantity indicator (if > 1) - show on right side
                        if mat.quantity > 1:
                            qty_text = self.tiny_font.render(f"x{mat.quantity}", True, (255, 255, 100))
                            qty_x = chip_rect.right - qty_text.get_width() - s(5)
                            surf.blit(qty_text, (qty_x, chip_rect.centery - qty_text.get_height() // 2))

                        abs_chip_rect = chip_rect.move(wx, wy)
                        placement_rects.append((abs_chip_rect, (slot_type, i)))

                # Add button (slot for new material)
                add_btn_x = slot_x + len(materials) * (s(120) + s(10))
                add_btn_rect = pygame.Rect(add_btn_x, type_y + s(5), s(60), s(25))
                is_add_hovered = add_btn_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))
                add_color = (60, 80, 100) if is_add_hovered else (50, 70, 90)
                pygame.draw.rect(surf, add_color, add_btn_rect, border_radius=s(3))
                add_text = self.tiny_font.render("+Add", True, (180, 200, 220))
                surf.blit(add_text, (add_btn_rect.centerx - add_text.get_width() // 2, add_btn_rect.centery - add_text.get_height() // 2))

                abs_add_rect = add_btn_rect.move(wx, wy)
                placement_rects.append((abs_add_rect, (slot_type, len(materials))))

                type_y += slot_h

        elif isinstance(interactive_ui, InteractiveAdornmentsUI):
            # SHAPE-BASED CARTESIAN SYSTEM (Adornments/Enchanting)
            header_text = f"PATTERN DESIGNER ({interactive_ui.grid_template})"
            surf.blit(self.small_font.render(header_text, True, (200, 200, 200)), (placement_x + s(10), placement_y + s(8)))

            # ==== LEFT CONTROLS: Shape Selection ====
            controls_x = placement_x + s(10)
            controls_y = placement_y + s(35)
            controls_w = s(180)

            # Shape selection title
            surf.blit(self.tiny_font.render("SHAPE TYPE:", True, (180, 180, 180)), (controls_x, controls_y))
            controls_y += s(18)

            # Get available shapes for this tier
            available_shapes = interactive_ui.get_available_shapes()
            shape_display_names = {
                "triangle_equilateral_small": "△ Equi (S)",
                "square_small": "□ Square (S)",
                "triangle_isosceles_small": "△ Isos (S)",
                "triangle_equilateral_large": "△ Equi (L)",
                "square_large": "□ Square (L)",
                "triangle_isosceles_large": "△ Isos (L)"
            }

            # Render shape buttons
            shape_btn_h = s(28)
            for shape_type in available_shapes:
                shape_btn_rect = pygame.Rect(controls_x, controls_y, controls_w, shape_btn_h)
                is_selected = interactive_ui.selected_shape_type == shape_type
                is_hovered = shape_btn_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))

                btn_color = (80, 100, 80) if is_selected else ((60, 75, 75) if is_hovered else (50, 60, 70))
                pygame.draw.rect(surf, btn_color, shape_btn_rect, border_radius=s(3))
                border_color = (120, 200, 120) if is_selected else (100, 120, 140)
                pygame.draw.rect(surf, border_color, shape_btn_rect, s(2) if is_selected else s(1), border_radius=s(3))

                btn_text = self.tiny_font.render(shape_display_names.get(shape_type, shape_type), True, (220, 220, 220))
                surf.blit(btn_text, (shape_btn_rect.x + s(8), shape_btn_rect.centery - btn_text.get_height() // 2))

                # Store for click detection
                abs_btn_rect = shape_btn_rect.move(wx, wy)
                placement_rects.append((abs_btn_rect, ('shape_select', shape_type)))

                controls_y += shape_btn_h + s(5)

            # Rotation controls
            controls_y += s(10)
            surf.blit(self.tiny_font.render("ROTATION:", True, (180, 180, 180)), (controls_x, controls_y))
            controls_y += s(18)

            rotation_text = f"{interactive_ui.selected_rotation}°"
            rotation_display = self.small_font.render(rotation_text, True, (220, 220, 220))
            surf.blit(rotation_display, (controls_x + controls_w // 2 - rotation_display.get_width() // 2, controls_y))
            controls_y += s(25)

            # Rotation buttons (- and +)
            rot_btn_w = s(60)
            rot_btn_h = s(30)
            rot_minus_rect = pygame.Rect(controls_x, controls_y, rot_btn_w, rot_btn_h)
            rot_plus_rect = pygame.Rect(controls_x + rot_btn_w + s(10), controls_y, rot_btn_w, rot_btn_h)

            for rot_rect, rot_label, rot_delta in [(rot_minus_rect, "◄ -45°", -45), (rot_plus_rect, "+45° ►", 45)]:
                is_hovered = rot_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))
                btn_color = (70, 90, 110) if is_hovered else (50, 70, 90)
                pygame.draw.rect(surf, btn_color, rot_rect, border_radius=s(3))
                pygame.draw.rect(surf, (120, 140, 160), rot_rect, s(1), border_radius=s(3))
                rot_text = self.tiny_font.render(rot_label, True, (200, 200, 200))
                surf.blit(rot_text, (rot_rect.centerx - rot_text.get_width() // 2, rot_rect.centery - rot_text.get_height() // 2))
                abs_rot_rect = rot_rect.move(wx, wy)
                placement_rects.append((abs_rot_rect, ('rotation', rot_delta)))

            # Shape list
            controls_y += rot_btn_h + s(15)
            surf.blit(self.tiny_font.render("PLACED SHAPES:", True, (180, 180, 180)), (controls_x, controls_y))
            controls_y += s(18)

            for i, shape in enumerate(interactive_ui.shapes):
                shape_item_rect = pygame.Rect(controls_x, controls_y, controls_w - s(35), s(22))
                is_hovered = shape_item_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))
                pygame.draw.rect(surf, (60, 70, 80) if is_hovered else (50, 60, 70), shape_item_rect, border_radius=s(2))
                shape_name = shape_display_names.get(shape['type'], shape['type'])[:12]
                shape_text = self.tiny_font.render(f"{i+1}. {shape_name}", True, (200, 200, 200))
                surf.blit(shape_text, (shape_item_rect.x + s(5), shape_item_rect.centery - shape_text.get_height() // 2))

                # Delete button
                del_btn_rect = pygame.Rect(controls_x + controls_w - s(30), controls_y, s(25), s(22))
                is_del_hovered = del_btn_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))
                del_color = (120, 60, 60) if is_del_hovered else (80, 50, 50)
                pygame.draw.rect(surf, del_color, del_btn_rect, border_radius=s(2))
                del_text = self.tiny_font.render("✕", True, (255, 200, 200))
                surf.blit(del_text, (del_btn_rect.centerx - del_text.get_width() // 2, del_btn_rect.centery - del_text.get_height() // 2))

                abs_del_rect = del_btn_rect.move(wx, wy)
                placement_rects.append((abs_del_rect, ('delete_shape', i)))

                controls_y += s(24)

            # ==== RIGHT SIDE: Cartesian Grid ====
            coord_range = interactive_ui.coordinate_range
            grid_size = coord_range * 2 + 1
            grid_area_w = placement_w - controls_w - s(40)
            grid_area_h = placement_h - s(60)
            cell_size = min(s(24), grid_area_w // grid_size, grid_area_h // grid_size)

            grid_width = grid_size * cell_size
            grid_height = grid_size * cell_size
            grid_offset_x = placement_x + controls_w + s(30) + (grid_area_w - grid_width) // 2
            grid_offset_y = placement_y + s(40) + (grid_area_h - grid_height) // 2

            # Helper function to convert Cartesian to pixel
            def cart_to_pixel(cart_x, cart_y):
                px = grid_offset_x + (cart_x + coord_range) * cell_size + cell_size // 2
                py = grid_offset_y + (coord_range - cart_y) * cell_size + cell_size // 2
                return (px, py)

            # Draw grid as dots at vertices (not filled squares)
            for y in range(grid_size):
                for x in range(grid_size):
                    cart_x = x - coord_range
                    cart_y = coord_range - y
                    px = grid_offset_x + x * cell_size + cell_size // 2
                    py = grid_offset_y + y * cell_size + cell_size // 2

                    is_origin = (cart_x == 0 and cart_y == 0)
                    is_axis = (cart_x == 0 or cart_y == 0)

                    # Draw dot at vertex position
                    if is_origin:
                        dot_color = (150, 150, 200)  # Bright blue for origin
                        dot_radius = s(4)
                    elif is_axis:
                        dot_color = (100, 100, 120)  # Medium gray for axes
                        dot_radius = s(3)
                    else:
                        dot_color = (70, 75, 80)     # Dark gray for regular vertices
                        dot_radius = s(2)

                    pygame.draw.circle(surf, dot_color, (px, py), dot_radius)

                    # Create click region for this grid vertex (for shape placement)
                    # Use larger rect for easier clicking
                    click_rect = pygame.Rect(px - cell_size // 2, py - cell_size // 2, cell_size, cell_size)
                    abs_click_rect = click_rect.move(wx, wy)
                    placement_rects.append((abs_click_rect, (cart_x, cart_y)))

            # Draw shape lines
            for shape in interactive_ui.shapes:
                vertices_str = shape['vertices']
                vertices = []
                for v_str in vertices_str:
                    parts = v_str.split(',')
                    vx, vy = int(parts[0]), int(parts[1])
                    vertices.append((vx, vy))

                # Draw lines between vertices
                for i in range(len(vertices)):
                    v1 = vertices[i]
                    v2 = vertices[(i + 1) % len(vertices)]
                    p1 = cart_to_pixel(v1[0], v1[1])
                    p2 = cart_to_pixel(v2[0], v2[1])
                    pygame.draw.line(surf, (100, 150, 200), p1, p2, s(2))

            # Draw vertices (dots at shape corners)
            for shape in interactive_ui.shapes:
                for v_str in shape['vertices']:
                    parts = v_str.split(',')
                    vx, vy = int(parts[0]), int(parts[1])
                    coord_key = f"{vx},{vy}"
                    placed_mat = interactive_ui.vertices.get(coord_key)

                    px, py = cart_to_pixel(vx, vy)

                    # Draw vertex circle
                    if placed_mat:
                        # Material assigned - larger colored dot
                        mat_def = mat_db.get_material(placed_mat.item_id)
                        tier_colors = {1: (150, 150, 170), 2: (120, 200, 120), 3: (120, 170, 255), 4: (200, 120, 255)}
                        vertex_color = tier_colors.get(mat_def.tier if mat_def else 1, (150, 150, 170))
                        pygame.draw.circle(surf, vertex_color, (px, py), s(6))
                        pygame.draw.circle(surf, (255, 255, 255), (px, py), s(6), s(1))

                        # Material icon (very small)
                        if mat_def:
                            icon_size = s(14)
                            image_cache = ImageCache.get_instance()
                            icon = image_cache.get_image(f"materials/{placed_mat.item_id}.png", target_size=(icon_size, icon_size))
                            if icon:
                                surf.blit(icon, (px - icon_size // 2, py - icon_size // 2))
                    else:
                        # Empty vertex - hollow circle
                        pygame.draw.circle(surf, (200, 200, 100), (px, py), s(5))
                        pygame.draw.circle(surf, (255, 255, 150), (px, py), s(5), s(2))

                    # Click detection for vertex
                    vertex_rect = pygame.Rect(px - s(8), py - s(8), s(16), s(16))
                    abs_vertex_rect = vertex_rect.move(wx, wy)
                    placement_rects.append((abs_vertex_rect, (vx, vy)))

            # Axis labels
            for x in range(-coord_range, coord_range + 1, max(1, coord_range // 2)):
                px, py = cart_to_pixel(x, -coord_range)
                label = self.tiny_font.render(str(x), True, (120, 120, 140))
                surf.blit(label, (px - label.get_width() // 2, py + s(8)))

            for y in range(-coord_range, coord_range + 1, max(1, coord_range // 2)):
                px, py = cart_to_pixel(-coord_range, y)
                label = self.tiny_font.render(str(y), True, (120, 120, 140))
                surf.blit(label, (px - label.get_width() - s(8), py - label.get_height() // 2))

            # Instructions
            inst_y = placement_y + s(25)
            instructions = [
                "1. Select shape & rotation",
                "2. Click grid to place shape",
                "3. Click vertices to assign materials"
            ]
            for inst in instructions:
                inst_text = self.tiny_font.render(inst, True, (150, 150, 170))
                surf.blit(inst_text, (grid_offset_x, inst_y))
                inst_y += s(13)

        # ==============================================================================
        # BOTTOM PANEL: Recipe Status + Buttons
        # ==============================================================================
        bottom_y = placement_rect.bottom + s(20)

        # Recipe status
        if interactive_ui.matched_recipe:
            recipe = interactive_ui.matched_recipe
            # Get output name
            if equip_db.is_equipment(recipe.output_id):
                output = equip_db.create_equipment_from_id(recipe.output_id)
                output_name = output.name if output else recipe.output_id
            else:
                mat = mat_db.get_material(recipe.output_id)
                output_name = mat.name if mat else recipe.output_id

            # Status message
            status_text = f"✓ RECIPE MATCHED: {output_name} (x{recipe.output_qty})"
            status_color = (100, 255, 100)
        else:
            status_text = "No recipe matched"
            status_color = (200, 200, 200)

        status_surf = self.font.render(status_text, True, status_color)
        surf.blit(status_surf, (placement_x, bottom_y))

        # Narrative input for INVENT feature (only shown when no recipe matched)
        narrative_rect = None
        if not interactive_ui.matched_recipe:
            narrative_y = bottom_y + s(30)
            narrative_x = placement_x
            narrative_w = placement_w - s(20)
            narrative_h = s(28)

            narrative_rect_local = pygame.Rect(narrative_x, narrative_y, narrative_w, narrative_h)

            # Input box background
            is_narrative_active = getattr(interactive_ui, 'narrative_input_active', False)
            bg_color = (50, 55, 70) if is_narrative_active else (35, 40, 50)
            pygame.draw.rect(surf, bg_color, narrative_rect_local, border_radius=s(3))

            # Border (highlight if active)
            border_color = (120, 180, 255) if is_narrative_active else (80, 90, 110)
            pygame.draw.rect(surf, border_color, narrative_rect_local, s(2), border_radius=s(3))

            # Label (small, above the box)
            label_text = "Describe your invention (optional):"
            label_surf = self.tiny_font.render(label_text, True, (150, 160, 180))
            surf.blit(label_surf, (narrative_x, narrative_y - s(14)))

            # Narrative text or placeholder
            narrative_text = getattr(interactive_ui, 'player_narrative', '') or ''
            if is_narrative_active:
                # Add blinking cursor
                import time
                if int(time.time() * 2) % 2 == 0:
                    narrative_text += "|"

            display_text = narrative_text or "Click to describe what you want to create..."
            text_color = (200, 200, 200) if narrative_text and not narrative_text.endswith("|") else (100, 110, 130)
            if is_narrative_active and not getattr(interactive_ui, 'player_narrative', ''):
                display_text = "|"
                text_color = (200, 200, 200)

            # Truncate if too long
            max_chars = narrative_w // 7  # Approximate character width
            if len(display_text) > max_chars:
                display_text = "..." + display_text[-(max_chars - 3):]

            text_surf = self.small_font.render(display_text, True, text_color)
            surf.blit(text_surf, (narrative_x + s(8), narrative_y + s(6)))

            # Store rect for click detection
            narrative_rect = narrative_rect_local.move(wx, wy)

        # Buttons (CLEAR, INSTANT CRAFT, MINIGAME)
        button_y = bottom_y + s(35) + (s(45) if not interactive_ui.matched_recipe else 0)
        button_w = s(150)
        button_h = s(40)
        button_spacing = s(20)

        button_rects = {}

        # CLEAR button (always enabled)
        clear_x = placement_x
        clear_rect = pygame.Rect(clear_x, button_y, button_w, button_h)
        is_clear_hovered = clear_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))
        clear_color = (100, 60, 60) if is_clear_hovered else (80, 50, 50)
        pygame.draw.rect(surf, clear_color, clear_rect, border_radius=s(5))
        pygame.draw.rect(surf, (180, 100, 100), clear_rect, s(2), border_radius=s(5))
        clear_text = self.small_font.render("CLEAR", True, (255, 200, 200))
        surf.blit(clear_text, (clear_rect.centerx - clear_text.get_width() // 2, clear_rect.centery - clear_text.get_height() // 2))
        button_rects['clear'] = clear_rect.move(wx, wy)

        # INSTANT CRAFT button (enabled if recipe matched)
        instant_x = clear_x + button_w + button_spacing
        instant_rect = pygame.Rect(instant_x, button_y, button_w, button_h)
        instant_enabled = interactive_ui.matched_recipe is not None
        is_instant_hovered = instant_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))

        if instant_enabled:
            instant_color = (60, 100, 60) if is_instant_hovered else (50, 80, 50)
            instant_border = (120, 180, 120)
            instant_text_color = (220, 255, 220)
        else:
            instant_color = (40, 40, 40)
            instant_border = (80, 80, 80)
            instant_text_color = (120, 120, 120)

        pygame.draw.rect(surf, instant_color, instant_rect, border_radius=s(5))
        pygame.draw.rect(surf, instant_border, instant_rect, s(2), border_radius=s(5))
        instant_text = self.small_font.render("INSTANT CRAFT", True, instant_text_color)
        surf.blit(instant_text, (instant_rect.centerx - instant_text.get_width() // 2, instant_rect.centery - instant_text.get_height() // 2 - s(5)))
        instant_sub = self.tiny_font.render("0 XP", True, instant_text_color)
        surf.blit(instant_sub, (instant_rect.centerx - instant_sub.get_width() // 2, instant_rect.centery + s(8)))
        button_rects['instant'] = instant_rect.move(wx, wy) if instant_enabled else None

        # MINIGAME button (enabled if recipe matched)
        minigame_x = instant_x + button_w + button_spacing
        minigame_rect = pygame.Rect(minigame_x, button_y, button_w, button_h)
        minigame_enabled = interactive_ui.matched_recipe is not None
        is_minigame_hovered = minigame_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))

        if minigame_enabled:
            minigame_color = (80, 100, 60) if is_minigame_hovered else (60, 80, 50)
            minigame_border = (140, 180, 120)
            minigame_text_color = (230, 255, 220)
        else:
            minigame_color = (40, 40, 40)
            minigame_border = (80, 80, 80)
            minigame_text_color = (120, 120, 120)

        pygame.draw.rect(surf, minigame_color, minigame_rect, border_radius=s(5))
        pygame.draw.rect(surf, minigame_border, minigame_rect, s(2), border_radius=s(5))
        minigame_text = self.small_font.render("MINIGAME", True, minigame_text_color)
        surf.blit(minigame_text, (minigame_rect.centerx - minigame_text.get_width() // 2, minigame_rect.centery - minigame_text.get_height() // 2 - s(5)))
        minigame_sub = self.tiny_font.render("1.5x XP", True, (255, 200, 100) if minigame_enabled else minigame_text_color)
        surf.blit(minigame_sub, (minigame_rect.centerx - minigame_sub.get_width() // 2, minigame_rect.centery + s(8)))
        button_rects['minigame'] = minigame_rect.move(wx, wy) if minigame_enabled else None

        # INVENT RECIPE button (enabled if NO recipe matched AND at least 2 materials placed)
        # This allows players to try inventing new recipes with novel combinations
        invent_x = minigame_x + button_w + button_spacing
        invent_rect = pygame.Rect(invent_x, button_y, button_w, button_h)

        # Count placed materials based on discipline type
        placed_count = 0
        if hasattr(interactive_ui, 'grid'):  # Smithing
            placed_count = len(interactive_ui.grid)
        elif hasattr(interactive_ui, 'slots') and isinstance(interactive_ui.slots, list):  # Alchemy
            placed_count = sum(1 for s in interactive_ui.slots if s is not None)
        elif hasattr(interactive_ui, 'slots') and isinstance(interactive_ui.slots, dict):  # Engineering
            placed_count = sum(len(mats) for mats in interactive_ui.slots.values())
        elif hasattr(interactive_ui, 'core_slots'):  # Refining
            placed_count = sum(1 for s in interactive_ui.core_slots if s is not None)
            placed_count += sum(1 for s in interactive_ui.surrounding_slots if s is not None)
        elif hasattr(interactive_ui, 'vertices'):  # Adornments
            placed_count = len(interactive_ui.vertices)

        # Enable if: no matched recipe AND at least 2 materials placed
        invent_enabled = (interactive_ui.matched_recipe is None) and (placed_count >= 2)
        is_invent_hovered = invent_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))

        if invent_enabled:
            invent_color = (100, 80, 140) if is_invent_hovered else (80, 60, 120)
            invent_border = (160, 140, 200)
            invent_text_color = (230, 220, 255)
        else:
            invent_color = (40, 40, 45)
            invent_border = (80, 80, 90)
            invent_text_color = (120, 120, 130)

        pygame.draw.rect(surf, invent_color, invent_rect, border_radius=s(5))
        pygame.draw.rect(surf, invent_border, invent_rect, s(2), border_radius=s(5))
        invent_text = self.small_font.render("INVENT", True, invent_text_color)
        surf.blit(invent_text, (invent_rect.centerx - invent_text.get_width() // 2, invent_rect.centery - invent_text.get_height() // 2 - s(5)))
        invent_sub = self.tiny_font.render("New Recipe?", True, (200, 180, 255) if invent_enabled else invent_text_color)
        surf.blit(invent_sub, (invent_rect.centerx - invent_sub.get_width() // 2, invent_rect.centery + s(8)))
        button_rects['invent'] = invent_rect.move(wx, wy) if invent_enabled else None

        # Blit to screen
        self.screen.blit(surf, (wx, wy))

        # Render any pending tooltips (after main surface is blitted)
        if self._pending_tooltips:
            # Show first tooltip only (avoid clutter)
            tooltip_text = self._pending_tooltips[0]
            self.render_tooltip(tooltip_text, mouse_pos)

        # Add narrative rect to button_rects for click handling
        button_rects['narrative'] = narrative_rect

        # Return click regions
        return {
            'window_rect': pygame.Rect(wx, wy, ww, wh),
            'material_rects': material_rects,
            'placement_rects': placement_rects,
            'button_rects': button_rects
        }

    def render_equipment_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        if not character.equipment_ui_open:
            return None

        ww, wh = Config.MENU_LARGE_W, Config.MENU_MEDIUM_H  # Increased width from MEDIUM to LARGE
        wx = Config.VIEWPORT_WIDTH - ww - Config.scale(20)  # Right-aligned with margin
        wy = Config.scale(50)

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 240))

        surf.blit(self.font.render("EQUIPMENT", True, (255, 215, 0)), (Config.scale(20), Config.scale(20)))
        surf.blit(self.small_font.render("[E or ESC] Close | [SHIFT+CLICK] to unequip", True, (180, 180, 180)),
                  (ww - Config.scale(350), Config.scale(20)))

        slot_size = Config.scale(80)
        s = Config.scale  # Shorthand for readability
        # Increased horizontal spacing to prevent overlap
        horizontal_offset = s(110)  # Increased from s(20) to prevent overlap
        slots_layout = {
            'helmet': (ww // 2 - slot_size // 2, s(70)),
            'mainHand': (ww // 2 - horizontal_offset - slot_size // 2, s(170)),
            'chestplate': (ww // 2 - slot_size // 2, s(170)),
            'offHand': (ww // 2 + horizontal_offset - slot_size // 2, s(170)),
            'gauntlets': (ww // 2 - horizontal_offset - slot_size // 2, s(270)),
            'leggings': (ww // 2 - slot_size // 2, s(270)),
            'boots': (ww // 2 - slot_size // 2, s(370)),
            'accessory': (ww // 2 + horizontal_offset - slot_size // 2, s(270)),
        }

        hovered_slot = None
        equipment_rects = {}

        for slot_name, (sx, sy) in slots_layout.items():
            slot_rect = pygame.Rect(sx, sy, slot_size, slot_size)
            equipment_rects[slot_name] = (slot_rect, wx, wy)
            item = character.equipment.slots.get(slot_name)

            is_hovered = slot_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))
            if is_hovered and item:
                hovered_slot = (slot_name, item)

            color = Config.COLOR_SLOT_FILLED if item else Config.COLOR_SLOT_EMPTY
            pygame.draw.rect(surf, color, slot_rect)
            border_color = Config.COLOR_SLOT_SELECTED if is_hovered else Config.COLOR_SLOT_BORDER
            pygame.draw.rect(surf, border_color, slot_rect, 2)

            if item:
                rarity_color = Config.RARITY_COLORS.get(item.rarity, (200, 200, 200))

                # Try to display equipment icon
                from rendering.image_cache import ImageCache
                icon_displayed = False
                if hasattr(item, 'item_id') and item.item_id and hasattr(item, 'item_type'):
                    # Determine subfolder based on item type
                    subfolder_map = {
                        'weapon': 'weapons',
                        'shield': 'weapons',
                        'armor': 'armor',
                        'tool': 'tools',
                        'accessory': 'accessories',
                        'station': 'stations'
                    }
                    subfolder = subfolder_map.get(item.item_type, 'weapons')
                    icon_path = f"{subfolder}/{item.item_id}.png"  # ImageCache adds items/ prefix
                    image_cache = ImageCache.get_instance()
                    icon_size = slot_size - s(12)
                    icon = image_cache.get_image(icon_path, (icon_size, icon_size))
                    if icon:
                        icon_x = sx + s(6)
                        icon_y = sy + s(6)
                        surf.blit(icon, (icon_x, icon_y))
                        icon_displayed = True

                # Fallback to colored rectangle if no icon
                if not icon_displayed:
                    inner_rect = pygame.Rect(sx + s(5), sy + s(5), slot_size - s(10), slot_size - s(10))
                    pygame.draw.rect(surf, rarity_color, inner_rect)

                # Draw tier badge (smaller, in corner)
                tier_text = f"T{item.tier}"
                tier_surf = self.small_font.render(tier_text, True, (255, 255, 255))
                tier_bg = pygame.Rect(sx + s(5), sy + s(5), tier_surf.get_width() + s(4), tier_surf.get_height() + s(2))
                pygame.draw.rect(surf, (0, 0, 0, 180), tier_bg)
                surf.blit(tier_surf, (sx + s(7), sy + s(6)))

            label_surf = self.tiny_font.render(slot_name, True, (150, 150, 150))
            surf.blit(label_surf, (sx + slot_size // 2 - label_surf.get_width() // 2, sy + slot_size + s(3)))

        stats_x = s(20)
        stats_y = s(470)
        surf.blit(self.font.render("Equipment Stats:", True, (200, 200, 200)), (stats_x, stats_y))
        stats_y += s(30)

        weapon_dmg = character.equipment.get_weapon_damage()
        surf.blit(self.small_font.render(f"Weapon Damage: {weapon_dmg[0]}-{weapon_dmg[1]}", True, (200, 200, 200)),
                  (stats_x, stats_y))
        stats_y += s(20)

        total_defense = character.equipment.get_total_defense()
        surf.blit(self.small_font.render(f"Total Defense: {total_defense}", True, (200, 200, 200)), (stats_x, stats_y))
        stats_y += s(20)

        stat_bonuses = character.equipment.get_stat_bonuses()
        if stat_bonuses:
            surf.blit(self.small_font.render("Bonuses:", True, (150, 150, 150)), (stats_x, stats_y))
            stats_y += s(18)
            for stat, value in stat_bonuses.items():
                surf.blit(self.tiny_font.render(f"  +{value:.1f}% {stat}", True, (100, 200, 100)),
                          (stats_x + s(10), stats_y))
                stats_y += s(16)

        self.screen.blit(surf, (wx, wy))

        if hovered_slot:
            slot_name, item = hovered_slot
            # Defer tooltip rendering to ensure it appears on top of all UI elements
            # Create a fake ItemStack to pass equipment data to the tooltip system
            from entities.components.inventory import ItemStack
            fake_stack = ItemStack(item_id=item.item_id, quantity=1)
            fake_stack.equipment_data = item
            self.pending_tooltip = (fake_stack, (mouse_pos[0], mouse_pos[1]), character, True)  # True = from equipment UI

        return pygame.Rect(wx, wy, ww, wh), equipment_rects

    def render_equipment_tooltip(self, item: EquipmentItem, mouse_pos: Tuple[int, int], character: Character,
                                 from_inventory: bool = False, crafted_stats: dict = None):
        s = Config.scale

        # Calculate height based on crafted_stats
        base_height = s(340)
        stats_height = 0
        if crafted_stats:
            stats_height = s(25) + (len(crafted_stats) * s(18))

        tw, th, pad = s(320), base_height + stats_height, s(10)
        x, y = mouse_pos[0] + s(15), mouse_pos[1] + s(15)
        if x + tw > Config.SCREEN_WIDTH:
            x = mouse_pos[0] - tw - s(15)
        if y + th > Config.SCREEN_HEIGHT:
            y = mouse_pos[1] - th - s(15)

        surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        surf.fill(Config.COLOR_TOOLTIP_BG)

        y_pos = pad
        color = Config.RARITY_COLORS.get(item.rarity, (200, 200, 200))

        surf.blit(self.font.render(item.name, True, color), (pad, y_pos))
        y_pos += s(25)
        surf.blit(self.small_font.render(f"Tier {item.tier} | {item.rarity.capitalize()} | {item.slot}", True, color),
                  (pad, y_pos))
        y_pos += s(25)

        # Display tags if present
        if hasattr(item, 'tags') and item.tags:
            tags_text = ", ".join(item.tags)
            surf.blit(self.tiny_font.render(f"Tags: {tags_text}", True, (150, 200, 255)), (pad, y_pos))
            y_pos += s(18)

        if item.damage[0] > 0:
            dmg = item.get_actual_damage()
            surf.blit(self.small_font.render(f"Damage: {dmg[0]}-{dmg[1]}", True, (200, 200, 200)), (pad, y_pos))
            y_pos += s(20)

            # Show range for weapons
            if item.range != 1.0:
                surf.blit(self.small_font.render(f"Range: {item.range}", True, (200, 200, 200)), (pad, y_pos))
                y_pos += s(20)

        if item.defense > 0:
            def_val = int(item.defense * item.get_effectiveness())
            surf.blit(self.small_font.render(f"Defense: {def_val}", True, (200, 200, 200)), (pad, y_pos))
            y_pos += s(20)

        if item.attack_speed != 1.0:
            surf.blit(self.small_font.render(f"Attack Speed: {item.attack_speed:.2f}x", True, (200, 200, 200)),
                      (pad, y_pos))
            y_pos += s(20)

        # Display enchantments
        if item.enchantments:
            y_pos += s(5)
            surf.blit(self.small_font.render("Enchantments:", True, (180, 140, 255)), (pad, y_pos))
            y_pos += s(20)
            for ench in item.enchantments:
                ench_name = ench.get('name', 'Unknown')
                effect = ench.get('effect', {})
                effect_type = effect.get('type', '')
                effect_value = effect.get('value', 0)

                # Format the enchantment display
                if effect_type == 'damage_multiplier':
                    ench_text = f"  {ench_name}: +{int(effect_value * 100)}% Damage"
                elif effect_type == 'durability_multiplier':
                    ench_text = f"  {ench_name}: +{int(effect_value * 100)}% Durability"
                elif effect_type == 'defense_multiplier':
                    ench_text = f"  {ench_name}: +{int(effect_value * 100)}% Defense"
                elif effect_type == 'speed_multiplier':
                    ench_text = f"  {ench_name}: +{int(effect_value * 100)}% Speed"
                else:
                    ench_text = f"  {ench_name}"

                surf.blit(self.tiny_font.render(ench_text, True, (200, 180, 255)), (pad, y_pos))
                y_pos += s(16)

        # Display crafted bonuses if present
        if crafted_stats:
            y_pos += s(5)
            surf.blit(self.small_font.render("Crafted Bonuses:", True, (100, 255, 100)), (pad, y_pos))
            y_pos += s(18)
            for stat_name, stat_value in crafted_stats.items():
                # Format stat name nicely (capitalize and add spaces)
                display_name = stat_name.replace('_', ' ').title()
                # Format value based on stat type
                if isinstance(stat_value, (int, float)):
                    # Multipliers (damage_multiplier, defense_multiplier, durability_multiplier) show as %
                    if 'multiplier' in stat_name:
                        value_str = f"+{int(stat_value*100)}%" if stat_value >= 0 else f"{int(stat_value*100)}%"
                    # Efficiency shows as multiplier (e.g., 1.2x)
                    elif stat_name == 'efficiency':
                        value_str = f"{stat_value:.2f}x"
                    # Quality shows as X/100
                    elif stat_name == 'quality':
                        value_str = f"{int(stat_value)}/100"
                    # Other numeric stats
                    else:
                        value_str = f"+{stat_value}" if stat_value >= 0 else str(stat_value)
                else:
                    value_str = str(stat_value)
                stat_text = f"  {display_name}: {value_str}"
                surf.blit(self.tiny_font.render(stat_text, True, (150, 220, 150)), (pad, y_pos))
                y_pos += s(16)

        dur_pct = (item.durability_current / item.durability_max) * 100
        dur_color = (100, 255, 100) if dur_pct > 50 else (255, 200, 100) if dur_pct > 25 else (255, 100, 100)
        dur_text = f"Durability: {item.durability_current}/{item.durability_max} ({dur_pct:.0f}%)"
        if Config.DEBUG_INFINITE_DURABILITY:
            dur_text += " (∞)"
        surf.blit(self.small_font.render(dur_text, True, dur_color), (pad, y_pos))
        y_pos += s(20)

        if item.requirements:
            y_pos += s(5)
            surf.blit(self.tiny_font.render("Requirements:", True, (150, 150, 150)), (pad, y_pos))
            y_pos += s(15)
            can_equip, reason = item.can_equip(character)
            req_color = (100, 255, 100) if can_equip else (255, 100, 100)
            if 'level' in item.requirements:
                surf.blit(self.tiny_font.render(f"  Level {item.requirements['level']}", True, req_color),
                          (pad + 10, y_pos))
                y_pos += 14
            if 'stats' in item.requirements:
                for stat, val in item.requirements['stats'].items():
                    surf.blit(self.tiny_font.render(f"  {stat}: {val}", True, req_color), (pad + 10, y_pos))
                    y_pos += 14

        # Show hint about equipping/unequipping
        y_pos += 5
        if from_inventory:
            hint = "[DOUBLE-CLICK] to equip"
        else:
            hint = "[SHIFT+CLICK] to unequip"
        surf.blit(self.tiny_font.render(hint, True, (150, 150, 255)), (pad, y_pos))

        self.screen.blit(surf, (x, y))

    def render_tool_tooltip(self, tool, tool_type: str, mouse_pos: Tuple[int, int], character: Character = None):
        """Render tooltip for equipped tool showing stats and durability."""
        s = Config.scale

        # Check for class bonus
        class_bonus = 0.0
        class_name = None
        if character and character.class_system and character.class_system.current_class:
            class_bonus = character.class_system.get_tool_efficiency_bonus(tool_type)
            if class_bonus > 0:
                class_name = character.class_system.current_class.name

        # Calculate tooltip dimensions (extra height if class bonus exists)
        tw = s(220)
        th = s(140) if class_bonus > 0 else s(120)

        # Position to the right of cursor
        x = mouse_pos[0] + s(15)
        y = mouse_pos[1]

        # Keep on screen
        if x + tw > Config.SCREEN_WIDTH:
            x = mouse_pos[0] - tw - s(15)
        if y + th > Config.SCREEN_HEIGHT:
            y = Config.SCREEN_HEIGHT - th - s(10)

        surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        surf.fill((25, 25, 35, 250))
        pygame.draw.rect(surf, (100, 120, 140), (0, 0, tw, th), s(2))

        pad = s(10)
        y_pos = pad

        # Tool name
        tool_name = getattr(tool, 'name', f"Tier {tool.tier} {tool_type.title()}")
        name_surf = self.font.render(tool_name, True, (255, 215, 0))
        surf.blit(name_surf, (pad, y_pos))
        y_pos += s(25)

        # Tier
        tier_surf = self.small_font.render(f"Tier: {tool.tier}", True, (180, 180, 180))
        surf.blit(tier_surf, (pad, y_pos))
        y_pos += s(20)

        # Damage
        damage_surf = self.small_font.render(f"Damage: {tool.damage}", True, (255, 150, 150))
        surf.blit(damage_surf, (pad, y_pos))
        y_pos += s(20)

        # Durability with color coding
        dur_pct = (tool.durability_current / tool.durability_max) if tool.durability_max > 0 else 0
        if dur_pct >= 0.5:
            dur_color = (100, 255, 100)  # Green
        elif dur_pct >= 0.25:
            dur_color = (255, 200, 100)  # Yellow
        else:
            dur_color = (255, 100, 100)  # Red

        dur_text = f"Durability: {tool.durability_current}/{tool.durability_max}"
        dur_surf = self.small_font.render(dur_text, True, dur_color)
        surf.blit(dur_surf, (pad, y_pos))
        y_pos += s(20)

        # Efficiency (base)
        eff_surf = self.tiny_font.render(f"Efficiency: {tool.efficiency:.0%}", True, (150, 200, 255))
        surf.blit(eff_surf, (pad, y_pos))
        y_pos += s(16)

        # Class bonus (if applicable)
        if class_bonus > 0 and class_name:
            bonus_text = f"  ({class_name} class: +{class_bonus*100:.0f}%)"
            bonus_surf = self.tiny_font.render(bonus_text, True, (100, 255, 150))
            surf.blit(bonus_surf, (pad, y_pos))

        self.screen.blit(surf, (x, y))

    def render_pending_tooltip(self):
        """Render any deferred tooltip - call this LAST in render loop to ensure tooltips appear on top."""
        # Handle class tooltips first
        if self.pending_class_tooltip is not None:
            class_def, mouse_pos = self.pending_class_tooltip
            self.pending_class_tooltip = None  # Clear for next frame
            self.render_class_tooltip(class_def, mouse_pos)

        # Handle tool tooltips
        if self.pending_tool_tooltip is not None:
            tool, tool_type, mouse_pos, character = self.pending_tool_tooltip
            self.pending_tool_tooltip = None  # Clear for next frame
            self.render_tool_tooltip(tool, tool_type, mouse_pos, character)

        if self.pending_tooltip is None:
            return

        item_stack, mouse_pos, character, is_equipment_ui = self.pending_tooltip
        self.pending_tooltip = None  # Clear for next frame

        if is_equipment_ui:
            # From equipment UI - render equipment tooltip
            equipment = item_stack.get_equipment() if item_stack else None
            if equipment:
                # Pass equipment.bonuses as crafted_stats to display crafted bonuses
                self.render_equipment_tooltip(equipment, mouse_pos, character, from_inventory=False,
                                             crafted_stats=equipment.bonuses)
        else:
            # From inventory - use render_item_tooltip
            self.render_item_tooltip(item_stack, mouse_pos, character)

    def render_class_tooltip(self, class_def, mouse_pos: Tuple[int, int]):
        """Render detailed tooltip for a class with tags and skill affinity explanation."""
        s = Config.scale

        # Calculate tooltip dimensions based on content
        # Description + Tags section + Skill Affinity + Preferred Types + Armor
        tag_count = len(class_def.tags) if class_def.tags else 0
        damage_type_count = len(class_def.preferred_damage_types) if class_def.preferred_damage_types else 0

        # Height calculation: title + description (2 lines) + spacing + tags header + tags + spacing
        # + skill affinity header + explanation (2 lines) + spacing + damage types + armor type
        base_height = s(40)  # Title and description
        tags_height = s(40 + 18) if tag_count > 0 else 0  # Header + tags line
        affinity_height = s(60)  # Skill affinity explanation
        damage_height = s(25) if damage_type_count > 0 else 0
        armor_height = s(25) if class_def.preferred_armor_type else 0

        tw = s(320)
        th = base_height + tags_height + affinity_height + damage_height + armor_height + s(30)

        # Position tooltip to the left of cursor since class cards are on the right
        x = mouse_pos[0] - tw - s(15)
        y = mouse_pos[1]

        # Keep on screen
        if x < 0:
            x = mouse_pos[0] + s(15)
        if y + th > Config.SCREEN_HEIGHT:
            y = Config.SCREEN_HEIGHT - th - s(10)

        surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        surf.fill((25, 25, 35, 250))
        pygame.draw.rect(surf, (100, 120, 140), (0, 0, tw, th), s(2))

        pad = s(10)
        y_pos = pad

        # Class name
        name_surf = self.font.render(class_def.name, True, (255, 215, 0))
        surf.blit(name_surf, (pad, y_pos))
        y_pos += s(25)

        # Description (truncated if too long)
        desc = class_def.description
        if len(desc) > 50:
            desc = desc[:47] + "..."
        desc_surf = self.small_font.render(desc, True, (180, 180, 180))
        surf.blit(desc_surf, (pad, y_pos))
        y_pos += s(22)

        # Tags section
        if class_def.tags:
            y_pos += s(5)
            surf.blit(self.small_font.render("Identity Tags:", True, (150, 200, 255)), (pad, y_pos))
            y_pos += s(18)
            tags_text = ", ".join(class_def.tags)
            surf.blit(self.tiny_font.render(tags_text, True, (130, 180, 230)), (pad + s(5), y_pos))
            y_pos += s(18)

        # Skill Affinity section
        y_pos += s(5)
        surf.blit(self.small_font.render("Skill Affinity Bonus:", True, (100, 255, 150)), (pad, y_pos))
        y_pos += s(18)
        surf.blit(self.tiny_font.render("Skills matching class tags get bonuses:", True, (180, 180, 180)),
                  (pad + s(5), y_pos))
        y_pos += s(14)
        surf.blit(self.tiny_font.render("1 tag = +5%, 2 = +10%, 3 = +15%, 4+ = +20% max", True, (100, 200, 100)),
                  (pad + s(5), y_pos))
        y_pos += s(18)

        # Preferred damage types
        if class_def.preferred_damage_types:
            y_pos += s(3)
            dmg_text = f"Preferred Damage: {', '.join(class_def.preferred_damage_types)}"
            surf.blit(self.tiny_font.render(dmg_text, True, (255, 180, 100)), (pad, y_pos))
            y_pos += s(16)

        # Preferred armor
        if class_def.preferred_armor_type:
            y_pos += s(3)
            armor_text = f"Preferred Armor: {class_def.preferred_armor_type.title()}"
            surf.blit(self.tiny_font.render(armor_text, True, (180, 180, 255)), (pad, y_pos))

        self.screen.blit(surf, (x, y))

    def render_enchantment_selection_ui(self, mouse_pos: Tuple[int, int], recipe: Recipe, compatible_items: List, scroll_offset: int = 0):
        """Render UI for selecting which item to apply enchantment to"""
        if not recipe or not compatible_items:
            return None

        ww, wh = 600, 500
        wx = Config.VIEWPORT_WIDTH - ww - 20  # Right-aligned with margin
        wy = 100

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((25, 25, 35, 250))

        # Title
        title_text = f"Apply {recipe.enchantment_name}"
        surf.blit(self.font.render(title_text, True, (255, 215, 0)), (20, 20))
        surf.blit(self.small_font.render("[ESC] Cancel | [SCROLL] Scroll | [CLICK] Select", True, (180, 180, 180)),
                  (ww - 320, 20))

        # Description
        y_pos = 60
        surf.blit(self.small_font.render(f"Select an item ({len(compatible_items)} compatible):", True, (200, 200, 200)), (20, y_pos))
        y_pos += 30

        # List compatible items with scrolling
        slot_size = 60
        item_rects = []
        visible_start = scroll_offset
        visible_end = visible_start + 20  # Show up to 20 items (more than fits, renderer will cut off)

        for list_idx in range(visible_start, min(visible_end, len(compatible_items))):
            source_type, source_id, item_stack, equipment = compatible_items[list_idx]

            if y_pos + slot_size + 10 > wh - 20:
                break  # Don't overflow window (now only breaks for visible items)

            item_rect = pygame.Rect(20, y_pos, ww - 40, slot_size + 10)
            rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
            is_hovered = item_rect.collidepoint(rx, ry)

            # Background
            bg_color = (50, 50, 70) if is_hovered else (35, 35, 50)
            pygame.draw.rect(surf, bg_color, item_rect)
            pygame.draw.rect(surf, (100, 100, 150) if is_hovered else (70, 70, 90), item_rect, 2)

            # Item icon/color
            icon_rect = pygame.Rect(30, y_pos + 5, slot_size, slot_size)
            rarity_color = Config.RARITY_COLORS.get(equipment.rarity, (200, 200, 200))
            pygame.draw.rect(surf, rarity_color, icon_rect)
            pygame.draw.rect(surf, (50, 50, 50), icon_rect, 2)

            # Tier
            tier_text = f"T{equipment.tier}"
            tier_surf = self.small_font.render(tier_text, True, (0, 0, 0))
            surf.blit(tier_surf, (35, y_pos + 10))

            # Item name and info
            name_x = 110
            surf.blit(self.small_font.render(equipment.name, True, (255, 255, 255)),
                     (name_x, y_pos + 10))

            # Location (inventory or equipped)
            location_text = f"[{source_type.upper()}]" if source_type == 'equipped' else f"[Inventory slot {source_id}]"
            surf.blit(self.tiny_font.render(location_text, True, (150, 150, 200)),
                     (name_x, y_pos + 35))

            # Show current enchantments if any
            if equipment.enchantments:
                enchant_count = len(equipment.enchantments)
                surf.blit(self.tiny_font.render(f"Enchantments: {enchant_count}", True, (100, 200, 200)),
                         (name_x, y_pos + 50))

            item_rects.append((item_rect, source_type, source_id, item_stack, equipment))
            y_pos += slot_size + 15

        self.screen.blit(surf, (wx, wy))
        window_rect = pygame.Rect(wx, wy, ww, wh)
        return window_rect, item_rects

    def render_start_menu(self, selected_option: int, mouse_pos: Tuple[int, int]):
        """Render the start menu with New World / Load World / Load Default Save / Temporary World options"""
        s = Config.scale
        # Menu dimensions (increased height for 4 options)
        ww = Config.MENU_SMALL_W
        wh = s(650)  # Increased from MENU_SMALL_H to fit 4 options
        wx = max(0, (Config.SCREEN_WIDTH - ww) // 2)  # Clamp to prevent off-screen
        wy = max(0, (Config.SCREEN_HEIGHT - wh) // 2)

        # Create menu surface
        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))
        pygame.draw.rect(surf, (100, 100, 120), surf.get_rect(), s(3))

        # Title
        title_text = self.font.render("WELCOME TO THE GAME", True, (255, 215, 0))
        title_rect = title_text.get_rect(centerx=ww // 2, y=s(40))
        surf.blit(title_text, title_rect)

        # Subtitle
        subtitle_text = self.small_font.render("Select an option to begin", True, (180, 180, 200))
        subtitle_rect = subtitle_text.get_rect(centerx=ww // 2, y=s(80))
        surf.blit(subtitle_text, subtitle_rect)

        # Menu options
        options = [
            ("New World", "Start a new adventure"),
            ("Load World", "Continue from a saved game"),
            ("Load Default Save", "Testing save with items & progress"),
            ("Temporary World", "Practice mode (no saves)")
        ]

        button_rects = []
        y_offset = s(120)  # Start buttons higher
        button_height = s(75)  # Slightly smaller buttons
        button_spacing = s(15)  # Tighter spacing

        for idx, (option_name, option_desc) in enumerate(options):
            button_rect = pygame.Rect(s(50), y_offset + idx * (button_height + button_spacing), ww - s(100), button_height)

            # Check hover and selection
            rx, ry = mouse_pos[0] - wx, mouse_pos[1] - wy
            is_hovered = button_rect.collidepoint(rx, ry)
            is_selected = (idx == selected_option)

            # Button background
            if is_hovered:
                bg_color = (80, 100, 140)
                border_color = (150, 180, 220)
            elif is_selected:
                bg_color = (60, 80, 120)
                border_color = (120, 140, 180)
            else:
                bg_color = (40, 50, 70)
                border_color = (80, 90, 110)

            pygame.draw.rect(surf, bg_color, button_rect)
            pygame.draw.rect(surf, border_color, button_rect, s(2))

            # Button text
            name_text = self.font.render(option_name, True, (220, 220, 240))
            name_rect = name_text.get_rect(centerx=button_rect.centerx, y=button_rect.y + s(15))
            surf.blit(name_text, name_rect)

            desc_text = self.small_font.render(option_desc, True, (160, 160, 180))
            desc_rect = desc_text.get_rect(centerx=button_rect.centerx, y=button_rect.y + s(45))
            surf.blit(desc_text, desc_rect)

            # Store button rect (in screen coordinates)
            button_rects.append(pygame.Rect(wx + button_rect.x, wy + button_rect.y, button_rect.width, button_rect.height))

        # Controls hint
        controls_text = self.small_font.render("[UP/DOWN] Navigate  [ENTER] Select  [MOUSE] Click", True, (140, 140, 160))
        controls_rect = controls_text.get_rect(centerx=ww // 2, y=wh - s(40))
        surf.blit(controls_text, controls_rect)

        # Check for existing saves
        if os.path.exists("saves"):
            save_files = [f for f in os.listdir("saves") if f.endswith(".json")]
            if save_files:
                save_count_text = self.tiny_font.render(f"Found {len(save_files)} save file(s)", True, (100, 200, 100))
                save_count_rect = save_count_text.get_rect(centerx=ww // 2, y=wh - s(70))
                surf.blit(save_count_text, save_count_rect)

        self.screen.blit(surf, (wx, wy))
        return button_rects

    def render_class_selection_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        if not character.class_selection_open:
            return None

        class_db = ClassDatabase.get_instance()
        if not class_db.loaded or not class_db.classes:
            return None

        s = Config.scale
        ww, wh = Config.MENU_LARGE_W, Config.MENU_LARGE_H
        wx = max(0, Config.VIEWPORT_WIDTH - ww - s(20))  # Right-aligned with margin, clamped
        wy = s(50)

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 250))

        surf.blit(self.font.render("SELECT YOUR CLASS", True, (255, 215, 0)), (ww // 2 - s(100), s(20)))
        surf.blit(self.small_font.render("Choose wisely - this defines your playstyle", True, (180, 180, 180)),
                  (ww // 2 - s(150), s(50)))

        classes_list = list(class_db.classes.values())
        col_width = (ww - s(60)) // 2
        card_height = s(90)

        class_buttons = []
        for idx, class_def in enumerate(classes_list):
            col = idx % 2
            row = idx // 2

            x = s(20) + col * (col_width + s(20))
            y = s(100) + row * (card_height + s(10))

            card_rect = pygame.Rect(x, y, col_width, card_height)
            is_hovered = card_rect.collidepoint((mouse_pos[0] - wx, mouse_pos[1] - wy))

            card_color = (60, 80, 100) if is_hovered else (40, 50, 60)
            pygame.draw.rect(surf, card_color, card_rect)
            pygame.draw.rect(surf, (100, 120, 140) if is_hovered else (80, 90, 100), card_rect, s(2))

            # Load and display class icon
            class_icon_path = f"classes/{class_def.class_id}.png"
            image_cache = ImageCache.get_instance()
            class_icon = image_cache.get_image(class_icon_path, (s(60), s(60)))

            # Determine text positioning based on icon availability
            if class_icon:
                # Icon on left side
                icon_rect = class_icon.get_rect(topleft=(x + s(10), y + s(10)))
                surf.blit(class_icon, icon_rect)
                # Text positioned to the right of icon
                text_x = x + s(80)  # After icon (10 + 60) + 10px spacing
                name_y = y + s(8)
                bonus_start_y = y + s(30)
            else:
                # No icon, use traditional left-aligned layout
                text_x = x + s(10)
                name_y = y + s(8)
                bonus_start_y = y + s(35)

            # Render class name
            name_surf = self.font.render(class_def.name, True, (255, 215, 0))
            surf.blit(name_surf, (text_x, name_y))

            # Render bonuses
            bonus_y = bonus_start_y
            for bonus_type, value in list(class_def.bonuses.items())[:2]:
                bonus_text = f"+{value if isinstance(value, int) else f'{value * 100:.0f}%'} {bonus_type.replace('_', ' ')}"
                bonus_surf = self.tiny_font.render(bonus_text, True, (100, 200, 100))
                surf.blit(bonus_surf, (text_x, bonus_y))
                bonus_y += s(14)

            if is_hovered:
                select_surf = self.small_font.render("[CLICK] Select", True, (100, 255, 100))
                surf.blit(select_surf, (x + col_width - select_surf.get_width() - s(10), y + card_height - s(25)))
                # Store class for deferred tooltip rendering (appears on top of all UI)
                self.pending_class_tooltip = (class_def, mouse_pos)

            class_buttons.append((card_rect, class_def))

        self.screen.blit(surf, (wx, wy))
        return pygame.Rect(wx, wy, ww, wh), class_buttons

    def render_stats_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        if not character.stats_ui_open:
            return None

        s = Config.scale
        ww, wh = Config.MENU_LARGE_W, Config.MENU_LARGE_H
        wx = max(0, Config.VIEWPORT_WIDTH - ww - s(20))  # Right-aligned with margin, clamped
        wy = s(50)

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 240))

        surf.blit(self.font.render(f"CHARACTER - Level {character.leveling.level}", True, (255, 215, 0)), (s(20), s(20)))
        surf.blit(self.small_font.render("[C or ESC] Close", True, (180, 180, 180)), (ww - s(150), s(20)))

        col1_x, col2_x, col3_x = s(20), s(320), s(620)
        y_start = s(70)

        y = y_start
        surf.blit(self.font.render("STATS", True, (255, 255, 255)), (col1_x, y))
        y += s(35)

        if character.leveling.unallocated_stat_points > 0:
            surf.blit(self.small_font.render(f"Points: {character.leveling.unallocated_stat_points}",
                                             True, (0, 255, 0)), (col1_x, y))
            y += s(25)

        stat_buttons = []
        for stat_name, label in [('strength', 'STR'), ('defense', 'DEF'), ('vitality', 'VIT'),
                                 ('luck', 'LCK'), ('agility', 'AGI'), ('intelligence', 'INT')]:
            val = getattr(character.stats, stat_name)
            bonus = character.stats.get_bonus(stat_name)
            surf.blit(self.small_font.render(f"{label}: {val} (+{bonus * 100:.0f}%)", True, (200, 200, 200)),
                      (col1_x, y))

            if character.leveling.unallocated_stat_points > 0:
                btn = pygame.Rect(col1_x + s(150), y - s(2), s(40), s(20))
                pygame.draw.rect(surf, (50, 100, 50), btn)
                pygame.draw.rect(surf, (100, 200, 100), btn, s(2))
                plus = self.small_font.render("+1", True, (255, 255, 255))
                surf.blit(plus, plus.get_rect(center=btn.center))
                stat_buttons.append((btn, stat_name))
            y += s(28)

        y = y_start
        surf.blit(self.font.render("TITLES", True, (255, 255, 255)), (col2_x, y))
        y += s(35)
        surf.blit(self.small_font.render(f"Earned: {len(character.titles.earned_titles)}",
                                         True, (200, 200, 200)), (col2_x, y))
        y += s(30)

        for title in character.titles.earned_titles[-8:]:
            tier_color = {
                'novice': (200, 200, 200), 'apprentice': (100, 255, 100), 'journeyman': (100, 150, 255),
                'expert': (200, 100, 255), 'master': (255, 215, 0)
            }.get(title.tier, (200, 200, 200))

            surf.blit(self.small_font.render(f"• {title.name}", True, tier_color), (col2_x, y))
            y += s(18)
            surf.blit(self.tiny_font.render(f"  {title.bonus_description}", True, (100, 200, 100)), (col2_x, y))
            y += s(20)

        if len(character.titles.earned_titles) == 0:
            surf.blit(self.small_font.render("Keep playing to earn titles!", True, (150, 150, 150)), (col2_x, y))

        y = y_start
        surf.blit(self.font.render("PROGRESS", True, (255, 255, 255)), (col3_x, y))
        y += s(35)

        title_db = TitleDatabase.get_instance()
        activities_shown = set()

        for activity_type in ['mining', 'forestry', 'smithing', 'refining', 'alchemy']:
            count = character.activities.get_count(activity_type)
            if count > 0 or activity_type in ['mining', 'forestry']:
                next_title = None
                for title_def in title_db.titles.values():
                    if title_def.activity_type == activity_type:
                        if not character.titles.has_title(title_def.title_id):
                            if count < title_def.acquisition_threshold:
                                if next_title is None or title_def.acquisition_threshold < next_title.acquisition_threshold:
                                    next_title = title_def

                if next_title and len(activities_shown) < 5:
                    activities_shown.add(activity_type)
                    progress = count / next_title.acquisition_threshold
                    surf.blit(self.small_font.render(f"{activity_type.capitalize()}:", True, (180, 180, 180)),
                              (col3_x, y))
                    y += s(18)

                    bar_w, bar_h = s(220), s(12)
                    bar_rect = pygame.Rect(col3_x, y, bar_w, bar_h)
                    pygame.draw.rect(surf, (40, 40, 40), bar_rect)
                    prog_w = int(bar_w * min(1.0, progress))
                    pygame.draw.rect(surf, (100, 200, 100), pygame.Rect(col3_x, y, prog_w, bar_h))
                    pygame.draw.rect(surf, (100, 100, 100), bar_rect, s(1))

                    prog_text = f"{count}/{next_title.acquisition_threshold}"
                    prog_surf = self.tiny_font.render(prog_text, True, (255, 255, 255))
                    surf.blit(prog_surf, (col3_x + bar_w // 2 - prog_surf.get_width() // 2, y + s(1)))
                    y += s(18)

                    next_surf = self.tiny_font.render(f"Next: {next_title.name}", True, (150, 150, 150))
                    surf.blit(next_surf, (col3_x, y))
                    y += s(22)

        if len(activities_shown) == 0:
            surf.blit(self.small_font.render("Start gathering and crafting!", True, (150, 150, 150)), (col3_x, y))

        self.screen.blit(surf, (wx, wy))
        return pygame.Rect(wx, wy, ww, wh), stat_buttons

    def render_tooltip(self, text: str, mouse_pos: Tuple[int, int], offset_x: int = 15, offset_y: int = 15):
        """
        Render a tooltip near the mouse cursor.

        Args:
            text: Text to display in tooltip
            mouse_pos: Current mouse position (x, y)
            offset_x: Horizontal offset from mouse (default 15px right)
            offset_y: Vertical offset from mouse (default 15px down)
        """
        if not text:
            return

        # Render text
        text_surf = self.small_font.render(text, True, (255, 255, 255))
        padding = 8
        tooltip_w = text_surf.get_width() + padding * 2
        tooltip_h = text_surf.get_height() + padding * 2

        # Position tooltip near mouse, with edge clamping
        tooltip_x = mouse_pos[0] + offset_x
        tooltip_y = mouse_pos[1] + offset_y

        # Clamp to screen bounds (total width = viewport + UI panel)
        screen_width = Config.VIEWPORT_WIDTH + Config.UI_PANEL_WIDTH
        screen_height = Config.VIEWPORT_HEIGHT

        if tooltip_x + tooltip_w > screen_width:
            tooltip_x = mouse_pos[0] - tooltip_w - 5
        if tooltip_y + tooltip_h > screen_height:
            tooltip_y = mouse_pos[1] - tooltip_h - 5

        # Draw tooltip background
        tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_w, tooltip_h)
        pygame.draw.rect(self.screen, (20, 20, 20, 230), tooltip_rect)
        pygame.draw.rect(self.screen, (200, 200, 100), tooltip_rect, 2)

        # Draw text
        self.screen.blit(text_surf, (tooltip_x + padding, tooltip_y + padding))

    def render_text(self, text: str, x: int, y: int, bold: bool = False, small: bool = False):
        font = self.small_font if small else self.font
        if bold:
            font.set_bold(True)
        surf = font.render(text, True, Config.COLOR_TEXT)
        self.screen.blit(surf, (x, y))
        if bold:
            font.set_bold(False)

    def _render_attack_effects(self, camera: 'Camera'):
        """Render attack effect visuals (lines, blocked indicators).

        Args:
            camera: Camera for world-to-screen coordinate conversion
        """
        try:
            from systems.attack_effects import get_attack_effects_manager, AttackEffectType
            from data.models.world import Position

            manager = get_attack_effects_manager()
            manager.update()  # Remove expired effects

            for effect in manager.get_active_effects():
                color = effect.get_color()

                # Convert positions to screen coordinates
                start_sx, start_sy = camera.world_to_screen(
                    Position(effect.start_pos[0], effect.start_pos[1], 0)
                )
                end_sx, end_sy = camera.world_to_screen(
                    Position(effect.end_pos[0], effect.end_pos[1], 0)
                )

                if effect.effect_type == AttackEffectType.LINE:
                    # Draw attack line
                    line_width = effect.get_line_width()

                    # Create a surface for alpha support
                    if color[3] > 0:  # Only draw if visible
                        pygame.draw.line(self.screen, color[:3], (start_sx, start_sy),
                                        (end_sx, end_sy), line_width)

                        # Draw small circle at impact point
                        impact_radius = max(2, line_width)
                        pygame.draw.circle(self.screen, color[:3], (end_sx, end_sy), impact_radius)

                elif effect.effect_type == AttackEffectType.BLOCKED:
                    # Draw blocked indicator (X mark)
                    size = int(Config.TILE_SIZE * 0.4 * effect.alpha)
                    if size > 2:
                        # Draw X
                        pygame.draw.line(self.screen, color[:3],
                                        (start_sx - size, start_sy - size),
                                        (start_sx + size, start_sy + size), 3)
                        pygame.draw.line(self.screen, color[:3],
                                        (start_sx + size, start_sy - size),
                                        (start_sx - size, start_sy + size), 3)

                        # Draw "BLOCKED" text if effect is fresh
                        if effect.alpha > 0.7:
                            blocked_surf = self.tiny_font.render("BLOCKED", True, color[:3])
                            self.screen.blit(blocked_surf,
                                           (start_sx - blocked_surf.get_width() // 2,
                                            start_sy - size - 15))

                elif effect.effect_type == AttackEffectType.AREA:
                    # Draw area effect circle
                    radius_world = effect.end_pos[0] - effect.start_pos[0]  # Stored in end_pos
                    radius_screen = int(radius_world * Config.TILE_SIZE)

                    if color[3] > 0 and radius_screen > 0:
                        # Draw expanding circle with fading alpha
                        pygame.draw.circle(self.screen, color[:3], (start_sx, start_sy),
                                         radius_screen, max(1, int(3 * effect.alpha)))

        except ImportError:
            # Attack effects module not available
            pass

    def render_loading_indicator(self):
        """
        Render a loading indicator. Shows either:
        - Full-screen overlay for LLM generation (overlay_mode=True)
        - Small corner indicator for classifier operations (overlay_mode=False)
        """
        try:
            from systems.llm_item_generator import get_loading_state
            loading_state = get_loading_state()

            if not loading_state.is_loading:
                return

            import time

            if loading_state.overlay_mode:
                # Full-screen loading overlay for LLM generation
                self._render_loading_overlay(loading_state, time.time())
            else:
                # Small corner indicator for classifier operations
                self._render_loading_corner(loading_state, time.time())

        except ImportError:
            # LLM module not available
            pass

    def _render_loading_overlay(self, loading_state, current_time: float):
        """Render a full-screen semi-transparent loading overlay with animation."""
        import math
        s = Config.scale

        # Check if in completion state
        is_complete = getattr(loading_state, 'is_complete', False)

        # Semi-transparent dark overlay
        overlay = pygame.Surface((Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 25, 180))
        self.screen.blit(overlay, (0, 0))

        # Center panel
        panel_width = s(400)
        panel_height = s(200)
        panel_x = (Config.VIEWPORT_WIDTH - panel_width) // 2
        panel_y = (Config.VIEWPORT_HEIGHT - panel_height) // 2

        # Panel background with gradient effect
        panel = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel.fill((20, 25, 45, 240))
        self.screen.blit(panel, (panel_x, panel_y))

        # Panel border with glow effect (green for complete, blue for loading)
        border_color = (80, 200, 120) if is_complete else (80, 120, 200)
        pygame.draw.rect(self.screen, border_color,
                        (panel_x, panel_y, panel_width, panel_height), 2)

        center_x = panel_x + panel_width // 2
        center_y = panel_y + s(60)
        elapsed = current_time - loading_state.start_time

        if is_complete:
            # COMPLETION STATE: Show checkmark
            checkmark_radius = s(35)

            # Animated scale for pop-in effect
            import time
            complete_time = getattr(loading_state, '_complete_time', current_time)
            anim_elapsed = current_time - complete_time
            scale_factor = min(1.0, anim_elapsed * 4)  # Pop in over 0.25 seconds
            scale_factor = 1 - (1 - scale_factor) ** 3  # Ease out

            # Draw checkmark circle (green)
            circle_color = (60, 180, 100)
            scaled_radius = int(checkmark_radius * scale_factor)
            pygame.draw.circle(self.screen, circle_color, (center_x, center_y), scaled_radius)

            # Draw checkmark (white)
            if scale_factor > 0.3:
                check_scale = min(1.0, (scale_factor - 0.3) / 0.7)
                # Checkmark points relative to center
                check_points = [
                    (center_x - s(15), center_y),
                    (center_x - s(5), center_y + s(12)),
                    (center_x + s(18), center_y - s(10))
                ]
                # Animate the checkmark drawing
                if check_scale > 0:
                    # Draw first part of checkmark
                    if check_scale > 0:
                        end_idx = min(check_scale, 0.5) * 2
                        p1 = check_points[0]
                        p2 = (
                            int(check_points[0][0] + (check_points[1][0] - check_points[0][0]) * min(1, end_idx)),
                            int(check_points[0][1] + (check_points[1][1] - check_points[0][1]) * min(1, end_idx))
                        )
                        pygame.draw.line(self.screen, (255, 255, 255), p1, p2, s(4))

                    # Draw second part of checkmark
                    if check_scale > 0.5:
                        end_idx = (check_scale - 0.5) * 2
                        p1 = check_points[1]
                        p2 = (
                            int(check_points[1][0] + (check_points[2][0] - check_points[1][0]) * min(1, end_idx)),
                            int(check_points[1][1] + (check_points[2][1] - check_points[1][1]) * min(1, end_idx))
                        )
                        pygame.draw.line(self.screen, (255, 255, 255), p1, p2, s(4))

        else:
            # LOADING STATE: Show animated spinner/orbs
            orb_radius = s(6)
            orbit_radius = s(30)
            num_orbs = 8

            for i in range(num_orbs):
                angle = (elapsed * 2 + i * (6.28 / num_orbs))
                orb_x = center_x + int(orbit_radius * math.cos(angle))
                orb_y = center_y + int(orbit_radius * math.sin(angle))

                # Fade orbs based on position (trailing effect)
                alpha = int(255 * (0.3 + 0.7 * ((i + elapsed * num_orbs) % num_orbs) / num_orbs))
                orb_color = (100 + int(50 * math.sin(elapsed + i)), 150, 255, min(255, alpha))

                # Draw orb with glow
                orb_surf = pygame.Surface((orb_radius * 3, orb_radius * 3), pygame.SRCALPHA)
                pygame.draw.circle(orb_surf, orb_color, (orb_radius * 3 // 2, orb_radius * 3 // 2), orb_radius)
                self.screen.blit(orb_surf, (orb_x - orb_radius * 3 // 2, orb_y - orb_radius * 3 // 2))

        # Main message
        message = loading_state.message or "Generating..."
        msg_color = (180, 255, 200) if is_complete else (220, 230, 255)
        msg_surf = self.font.render(message, True, msg_color)
        msg_x = center_x - msg_surf.get_width() // 2
        msg_y = panel_y + s(110)
        self.screen.blit(msg_surf, (msg_x, msg_y))

        # Subtitle (only when not complete)
        if not is_complete:
            subtitle = loading_state.subtitle
            if subtitle:
                sub_surf = self.small_font.render(subtitle, True, (150, 160, 190))
                sub_x = center_x - sub_surf.get_width() // 2
                sub_y = msg_y + s(30)
                self.screen.blit(sub_surf, (sub_x, sub_y))

            # Animated dots
            num_dots = int((elapsed * 2) % 4)
            dots = "." * num_dots
            dots_surf = self.small_font.render(dots, True, (150, 160, 190))
            self.screen.blit(dots_surf, (center_x + msg_surf.get_width() // 2 + s(5), msg_y))

        # Progress bar
        bar_width = panel_width - s(60)
        bar_height = s(8)
        bar_x = panel_x + s(30)
        bar_y = panel_y + panel_height - s(35)

        # Bar background
        pygame.draw.rect(self.screen, (30, 35, 55), (bar_x, bar_y, bar_width, bar_height))

        # Get animated progress (smooth animation from 0% to 90% over time)
        if hasattr(loading_state, 'get_animated_progress'):
            progress = loading_state.get_animated_progress()
        else:
            progress = loading_state.progress

        if progress > 0 or is_complete:
            # Determinate progress bar
            fill_width = int(bar_width * progress)
            # Green for complete, blue-to-cyan gradient for loading
            if is_complete:
                fill_color = (80, 200, 120)
            else:
                fill_color = (
                    int(80 + 40 * progress),
                    int(150 + 50 * progress),
                    255
                )
            pygame.draw.rect(self.screen, fill_color, (bar_x, bar_y, fill_width, bar_height))

            # Add shimmer effect for visual interest
            if not is_complete and progress < 1.0:
                shimmer_pos = int((elapsed * 100) % fill_width) if fill_width > 0 else 0
                if shimmer_pos > 0 and shimmer_pos < fill_width:
                    shimmer_width = min(s(20), fill_width - shimmer_pos)
                    for i in range(shimmer_width):
                        alpha = int(80 * math.sin(math.pi * i / shimmer_width))
                        shimmer_surf = pygame.Surface((1, bar_height), pygame.SRCALPHA)
                        shimmer_surf.fill((255, 255, 255, alpha))
                        self.screen.blit(shimmer_surf, (bar_x + shimmer_pos + i, bar_y))
        else:
            # Indeterminate animation (sliding highlight) - fallback
            pattern_width = s(60)
            offset = int((elapsed * 150) % (bar_width + pattern_width)) - pattern_width

            # Create gradient highlight
            for i in range(pattern_width):
                alpha = int(180 * math.sin(math.pi * i / pattern_width))
                px = bar_x + offset + i
                if bar_x <= px < bar_x + bar_width:
                    line_color = (100, 180, 255, alpha)
                    line_surf = pygame.Surface((1, bar_height), pygame.SRCALPHA)
                    line_surf.fill(line_color)
                    self.screen.blit(line_surf, (px, bar_y))

        # Bar border (green for complete, blue for loading)
        bar_border_color = (80, 180, 120) if is_complete else (60, 80, 120)
        pygame.draw.rect(self.screen, bar_border_color, (bar_x, bar_y, bar_width, bar_height), 1)

    def _render_loading_corner(self, loading_state, current_time: float):
        """Render a small loading indicator in the bottom-right corner."""
        # Position in bottom-right corner
        padding = 20
        indicator_width = 280
        # Adjust height based on whether we have a subtitle
        has_subtitle = loading_state.subtitle and len(loading_state.subtitle) > 0
        indicator_height = 70 if has_subtitle else 50
        x = Config.VIEWPORT_WIDTH - indicator_width - padding
        y = Config.VIEWPORT_HEIGHT - indicator_height - padding

        # Background with rounded corners effect
        bg_rect = pygame.Rect(x, y, indicator_width, indicator_height)
        bg_surface = pygame.Surface((indicator_width, indicator_height), pygame.SRCALPHA)
        bg_surface.fill((20, 20, 40, 220))
        self.screen.blit(bg_surface, (x, y))

        # Border
        pygame.draw.rect(self.screen, (100, 150, 255), bg_rect, 2)

        # Loading message (truncate if too long)
        message = loading_state.message or "Loading..."
        if len(message) > 30:
            message = message[:27] + "..."
        msg_surf = self.small_font.render(message, True, (200, 220, 255))
        self.screen.blit(msg_surf, (x + 10, y + 8))

        # Subtitle (if present)
        text_y_offset = 26  # Start after message
        if has_subtitle:
            subtitle = loading_state.subtitle
            if len(subtitle) > 35:
                subtitle = subtitle[:32] + "..."
            sub_surf = self.tiny_font.render(subtitle, True, (150, 160, 190))
            self.screen.blit(sub_surf, (x + 10, y + text_y_offset))
            text_y_offset += 18  # Move bar down for subtitle

        # Progress bar
        progress = loading_state.progress
        bar_x = x + 10
        bar_y = y + text_y_offset + 4
        bar_width = indicator_width - 20
        bar_height = 10

        # Bar background
        pygame.draw.rect(self.screen, (40, 40, 60), (bar_x, bar_y, bar_width, bar_height))

        # Bar fill (animated gradient)
        anim_offset = (current_time * 2) % 1.0  # Pulse animation

        if progress > 0:
            fill_width = int(bar_width * progress)
            # Gradient color based on progress
            r = int(100 + 100 * (1 - progress))
            g = int(150 + 100 * progress)
            b = 255
            pygame.draw.rect(self.screen, (r, g, b), (bar_x, bar_y, fill_width, bar_height))
        else:
            # Indeterminate loading animation (scrolling bar)
            pattern_width = 30
            offset = int(anim_offset * pattern_width * 2)
            # Create a clipping surface to ensure animation stays within bar bounds
            bar_clip_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
            for i in range(-1, bar_width // pattern_width + 2):
                px = bar_x + i * pattern_width + offset
                color = (100, 150, 255)
                stripe_rect = pygame.Rect(px, bar_y, pattern_width // 2, bar_height)
                stripe_rect = stripe_rect.clip(bar_clip_rect)
                if stripe_rect.width > 0:
                    pygame.draw.rect(self.screen, color, stripe_rect)

        # Bar border (keeps everything contained)
        pygame.draw.rect(self.screen, (60, 80, 120), (bar_x, bar_y, bar_width, bar_height), 1)
