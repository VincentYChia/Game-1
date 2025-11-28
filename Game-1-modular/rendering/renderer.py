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


class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        # Scaled fonts for responsive UI
        self.font = pygame.font.Font(None, Config.scale(24))
        self.small_font = pygame.font.Font(None, Config.scale(18))
        self.tiny_font = pygame.font.Font(None, Config.scale(14))

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
                    mat_name = (mat.name[:6] if mat else mat_id[:6])  # Truncate to fit
                    text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
                    text_rect = text_surf.get_rect(center=cell_rect.center)
                    surf.blit(text_surf, text_rect)
                elif has_recipe_requirement:
                    # Show what recipe requires (semi-transparent hint)
                    req_mat_id = recipe_placement_map[recipe_key]
                    mat = mat_db.get_material(req_mat_id)
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
        - Station tier determines number of slots (T1=3 slots, T2=5, T3=7, T4=9)
        - Core slots in center (hub)
        - Surrounding slots in circle around core (spokes)
        - User can place materials in slots

        Returns: Dict mapping slot rects to slot_id for click handling
        """
        mat_db = MaterialDatabase.get_instance()
        placement_db = PlacementDatabase.get_instance()

        # Determine slot counts based on station tier
        # T1: 1 core + 2 surrounding = 3 total
        # T2: 1 core + 4 surrounding = 5 total
        # T3: 1 core + 6 surrounding = 7 total
        # T4: 1 core + 8 surrounding = 9 total
        core_slots = 1
        surrounding_slots = 2 + (station_tier - 1) * 2

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
        core_radius = 40  # Radius of core slot
        surrounding_radius = 30  # Radius of each surrounding slot
        orbit_radius = 120  # Distance from center to surrounding slots

        slot_rects = []  # Will store list of (pygame.Rect, slot_id) for click detection

        # Draw core slot
        core_x = center_x - core_radius
        core_y = center_y - core_radius
        core_rect = pygame.Rect(core_x, core_y, core_radius * 2, core_radius * 2)

        # Determine core slot state
        has_user_core = "core_0" in user_placement
        has_required_core = len(required_core) > 0

        core_color = (50, 70, 50) if has_user_core else ((70, 60, 40) if has_required_core else (30, 30, 40))
        is_hovered = core_rect.collidepoint(mouse_pos)
        if is_hovered:
            core_color = tuple(min(255, c + 20) for c in core_color)

        pygame.draw.circle(surf, core_color, (center_x, center_y), core_radius)
        pygame.draw.circle(surf, (150, 130, 80), (center_x, center_y), core_radius, 2 if is_hovered else 1)

        # Draw core material
        if has_user_core:
            mat_id = user_placement["core_0"]
            mat = mat_db.get_material(mat_id)
            mat_name = (mat.name[:8] if mat else mat_id[:8])
            text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
            text_rect = text_surf.get_rect(center=(center_x, center_y))
            surf.blit(text_surf, text_rect)
        elif has_required_core:
            req_mat_id = required_core[0].get('materialId', '')
            mat = mat_db.get_material(req_mat_id)
            mat_name = (mat.name[:8] if mat else req_mat_id[:8])
            text_surf = self.tiny_font.render(mat_name, True, (180, 160, 120))
            text_rect = text_surf.get_rect(center=(center_x, center_y))
            surf.blit(text_surf, text_rect)

        slot_rects.append((core_rect, "core_0"))

        # Draw surrounding slots in circle
        import math
        for i in range(surrounding_slots):
            angle = (2 * math.pi * i) / surrounding_slots - math.pi / 2  # Start at top
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
                mat_name = (mat.name[:6] if mat else mat_id[:6])
                text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
                text_rect = text_surf.get_rect(center=(slot_x, slot_y))
                surf.blit(text_surf, text_rect)
            elif has_required_surrounding:
                req_mat_id = required_surrounding[i].get('materialId', '')
                mat = mat_db.get_material(req_mat_id)
                mat_name = (mat.name[:6] if mat else req_mat_id[:6])
                text_surf = self.tiny_font.render(mat_name, True, (180, 160, 120))
                text_rect = text_surf.get_rect(center=(slot_x, slot_y))
                surf.blit(text_surf, text_rect)

            slot_rects.append((slot_rect, slot_id))

        # Draw label
        label = f"Refining Hub: {core_slots} core + {surrounding_slots} surrounding (T{station_tier})"
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

            # Draw material name
            if has_user_material:
                mat_id = user_placement[slot_id]
                mat = mat_db.get_material(mat_id)
                mat_name = (mat.name[:10] if mat else mat_id[:10])
                text_surf = self.tiny_font.render(mat_name, True, (200, 255, 200))
                text_rect = text_surf.get_rect(center=(slot_rect.centerx, slot_rect.centery + 15))
                surf.blit(text_surf, text_rect)
            elif has_requirement:
                req_mat_id = required_for_slot.get('materialId', '')
                mat = mat_db.get_material(req_mat_id)
                mat_name = (mat.name[:10] if mat else req_mat_id[:10])
                text_surf = self.tiny_font.render(mat_name, True, (180, 160, 120))
                text_rect = text_surf.get_rect(center=(slot_rect.centerx, slot_rect.centery + 15))
                surf.blit(text_surf, text_rect)

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

                # Draw material name (right side)
                mat_id = required_slot.get('materialId', '')
                mat = mat_db.get_material(mat_id)
                mat_name = mat.name if mat else mat_id

                if has_user_material:
                    # Show user's material (green)
                    user_mat_id = user_placement[slot_id]
                    user_mat = mat_db.get_material(user_mat_id)
                    user_mat_name = user_mat.name if user_mat else user_mat_id
                    mat_surf = self.small_font.render(user_mat_name, True, (200, 255, 200))
                else:
                    # Show required material (gold hint)
                    mat_surf = self.small_font.render(mat_name, True, (180, 160, 120))

                surf.blit(mat_surf, (slot_rect.x + 120, slot_rect.y + 10))

                # Draw quantity
                qty = required_slot.get('quantity', 1)
                qty_surf = self.small_font.render(f"x{qty}", True, (150, 150, 150))
                surf.blit(qty_surf, (slot_rect.x + slot_width - 60, slot_rect.y + 10))

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

            # Draw NPC with sprite color
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
            color = station.get_color() if in_range else tuple(max(0, c - 50) for c in station.get_color())
            size = Config.TILE_SIZE + 8  # Larger than before (was - 8, now + 8)
            pts = [(sx, sy - size // 2), (sx + size // 2, sy), (sx, sy + size // 2), (sx - size // 2, sy)]
            pygame.draw.polygon(self.screen, color, pts)
            pygame.draw.polygon(self.screen, (0, 0, 0), pts, 3)
            if in_range:
                tier_text = f"T{station.tier}"
                tier_surf = self.small_font.render(tier_text, True, (255, 255, 255))
                tier_rect = tier_surf.get_rect(center=(sx, sy))
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

            # Render entity (turret icon or colored square)
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

        for resource in world.get_visible_resources(camera.position, Config.VIEWPORT_WIDTH, Config.VIEWPORT_HEIGHT):
            if resource.depleted and not resource.respawns:
                continue
            sx, sy = camera.world_to_screen(resource.position)
            in_range = character.is_in_range(resource.position)

            can_harvest, reason = character.can_harvest_resource(resource) if in_range else (False, "")

            size = Config.TILE_SIZE - 4
            rect = pygame.Rect(sx - size // 2, sy - size // 2, size, size)

            # Auto-generate icon path from resource type
            resource_icon_path = f"resources/{resource.resource_type.value}.png"

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

        for dmg in damage_numbers:
            sx, sy = camera.world_to_screen(dmg.position)
            alpha = int(255 * (dmg.lifetime / 1.0))
            color = Config.COLOR_DAMAGE_CRIT if dmg.is_crit else Config.COLOR_DAMAGE_NORMAL
            text = f"{dmg.damage}!" if dmg.is_crit else str(dmg.damage)
            surf = (self.font if dmg.is_crit else self.small_font).render(text, True, color)
            surf.set_alpha(alpha)
            self.screen.blit(surf, surf.get_rect(center=(sx, sy)))

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

    def render_ui(self, character: Character, mouse_pos: Tuple[int, int]):
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
            class_text = f"Class: {character.class_system.current_class.name}"
            self.render_text(class_text, Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 25

        self.render_text(f"Position: ({character.position.x:.1f}, {character.position.y:.1f})",
                         Config.VIEWPORT_WIDTH + 20, y, small=True)
        y += 25

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
            self.render_text(f"{tool.name} (T{tool.tier})", Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 20
            dur_text = f"Durability: {tool.durability_current}/{tool.durability_max}"
            if Config.DEBUG_INFINITE_RESOURCES:
                dur_text += " (∞)"
            self.render_text(dur_text, Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 20
            self.render_text(f"Effectiveness: {tool.get_effectiveness() * 100:.0f}%",
                             Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 30

        title_count = len(character.titles.earned_titles)
        self.render_text(f"TITLES: {title_count}", Config.VIEWPORT_WIDTH + 20, y, bold=True)
        y += 30
        for title in character.titles.earned_titles[-2:]:
            self.render_text(f"• {title.name}", Config.VIEWPORT_WIDTH + 20, y, small=True)
            y += 18

        if title_count > 0:
            y += 10

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
            "F1 - Debug Mode",
            "F2/F3/F4 - Debug Skills/Titles/Stats",
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

                        # Skill name (abbreviated)
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
                # Skill abbreviation
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

            # Skill name
            surf.blit(self.small_font.render(skill_def.name, True, (255, 255, 255)), (s(30), y_pos + s(5)))

            # Tier and rarity
            tier_color = {1: (150, 150, 150), 2: (100, 200, 100), 3: (200, 100, 200), 4: (255, 200, 50)}.get(skill_def.tier, (150, 150, 150))
            surf.blit(self.tiny_font.render(f"T{skill_def.tier} {skill_def.rarity.upper()}", True, tier_color), (s(30), y_pos + s(25)))

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

                # Skill name
                surf.blit(self.small_font.render(skill_def.name, True, (200, 255, 200)), (s(30), y_pos + s(5)))

                # Tier
                tier_color = {1: (150, 150, 150), 2: (100, 200, 100), 3: (200, 100, 200), 4: (255, 200, 50)}.get(skill_def.tier, (150, 150, 150))
                surf.blit(self.tiny_font.render(f"T{skill_def.tier}", True, tier_color), (s(30), y_pos + s(25)))

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

        # Tabs
        tab_y = s(80)
        tab_width = s(140)
        tab_height = s(40)
        tab_spacing = s(10)
        tabs = [
            ("guide", "GAME GUIDE"),
            ("quests", "QUESTS"),
            ("skills", "SKILLS"),
            ("titles", "TITLES")
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

        self.screen.blit(surf, (wx, wy))
        window_rect = pygame.Rect(wx, wy, ww, wh)
        self.encyclopedia_window_rect = window_rect  # Store for mouse wheel scrolling
        return window_rect, tab_rects

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

                    # Quest title
                    title_surf = self.small_font.render(quest_def.title, True, (220, 220, 255))
                    surf.blit(title_surf, (button_rect.x + s(10), button_rect.y + s(8)))

                    # Quest description (truncated)
                    desc = quest_def.description[:60] + "..." if len(quest_def.description) > 60 else quest_def.description
                    desc_surf = self.tiny_font.render(desc, True, (180, 180, 200))
                    surf.blit(desc_surf, (button_rect.x + s(10), button_rect.y + s(30)))

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
                # Quest Title
                if y >= content_rect.y - s(25) and y < content_rect.bottom:
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

                # Skill name
                name_color = (100, 255, 100) if has_skill else ((200, 200, 100) if can_learn else (150, 150, 150))
                status_text = " [KNOWN]" if has_skill else (" [AVAILABLE]" if can_learn else "")
                if y >= content_rect.y and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(f"• {skill_def.name}{status_text}", True, name_color), (x + s(10), y))
                y += s(16)

                # Requirements
                req_text = f"   Requires: Lvl {skill_def.requirements.character_level}"
                if skill_def.requirements.stats:
                    stat_reqs = ", ".join(f"{k} {v}" for k, v in skill_def.requirements.stats.items())
                    req_text += f", {stat_reqs}"
                if y >= content_rect.y and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(req_text, True, (120, 120, 140)), (x + s(10), y))
                y += s(16)

                # Effect description
                effect_desc = f"   {skill_def.effect.effect_type.capitalize()} - {skill_def.effect.category} ({skill_def.effect.magnitude})"
                if y >= content_rect.y and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(effect_desc, True, (100, 150, 200)), (x + s(10), y))
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

                # Title name
                if y >= content_rect.y and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(f"• {title_def.name}{status_text}", True, name_color), (x + s(10), y))
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
                req_text = f"   Requires: {title_def.acquisition_threshold} {activity_name}"
                if title_def.acquisition_method == "random_drop":
                    tier_chances = {'apprentice': '20%', 'journeyman': '10%', 'expert': '5%', 'master': '2%'}
                    chance = tier_chances.get(tier_name, '?%')
                    req_text += f" ({chance} chance)"
                if y >= content_rect.y and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(req_text, True, (120, 120, 140)), (x + s(10), y))
                y += s(16)

                # Bonus
                if y >= content_rect.y and y < content_rect.bottom:
                    surf.blit(self.tiny_font.render(f"   {title_def.bonus_description}", True, (100, 200, 100)), (x + s(10), y))
                y += s(20)

            y += s(10)

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

    def render_inventory_panel(self, character: Character, mouse_pos: Tuple[int, int]):
        panel_rect = pygame.Rect(Config.INVENTORY_PANEL_X, Config.INVENTORY_PANEL_Y,
                                 Config.INVENTORY_PANEL_WIDTH, Config.INVENTORY_PANEL_HEIGHT)
        pygame.draw.rect(self.screen, Config.COLOR_UI_BG, panel_rect)
        self.render_text("INVENTORY", 20, Config.INVENTORY_PANEL_Y + 10, bold=True)

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
        pygame.draw.rect(self.screen, Config.COLOR_SLOT_FILLED if equipped_axe else Config.COLOR_SLOT_EMPTY, axe_rect)
        pygame.draw.rect(self.screen, Config.COLOR_EQUIPPED if equipped_axe else Config.COLOR_SLOT_BORDER, axe_rect, 2)

        if equipped_axe:
            # Show tier and name
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
        pygame.draw.rect(self.screen, Config.COLOR_SLOT_FILLED if equipped_pick else Config.COLOR_SLOT_EMPTY, pick_rect)
        pygame.draw.rect(self.screen, Config.COLOR_EQUIPPED if equipped_pick else Config.COLOR_SLOT_BORDER, pick_rect, 2)

        if equipped_pick:
            # Show tier and name
            tier_surf = self.tiny_font.render(f"T{equipped_pick.tier}", True, (255, 255, 255))
            self.screen.blit(tier_surf, (pick_x + 5, tools_y + 5))
            name_surf = self.tiny_font.render("Pick", True, (255, 255, 255))
            self.screen.blit(name_surf, (pick_x + 5, tools_y + slot_size - 15))
        else:
            # Show empty slot label
            label_surf = self.tiny_font.render("Pick", True, (100, 100, 100))
            self.screen.blit(label_surf, (pick_x + 8, tools_y + 18))

        start_x, start_y = 20, tools_y + slot_size + 20
        slot_size, spacing = Config.INVENTORY_SLOT_SIZE, 5
        slots_per_row = Config.INVENTORY_SLOTS_PER_ROW
        hovered_slot = None

        for i, item_stack in enumerate(character.inventory.slots):
            row, col = i // slots_per_row, i % slots_per_row
            x, y = start_x + col * (slot_size + spacing), start_y + row * (slot_size + spacing)
            slot_rect = pygame.Rect(x, y, slot_size, slot_size)
            is_hovered = slot_rect.collidepoint(mouse_pos)

            if is_hovered and item_stack:
                hovered_slot = (i, item_stack, slot_rect)

            # Check if item is equipped
            is_equipped = False
            if item_stack and item_stack.is_equipment():
                is_equipped = character.equipment.is_equipped(item_stack.item_id)

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
            self.render_item_tooltip(item_stack, mouse_pos, character)

    def render_item_in_slot(self, item_stack: ItemStack, rect: pygame.Rect, is_equipped: bool = False):
        """
        Render an item in an inventory slot with optional image support.
        Falls back to colored rectangles if no image is available.
        """
        image_cache = ImageCache.get_instance()
        inner = pygame.Rect(rect.x + 5, rect.y + 5, rect.width - 10, rect.height - 10)

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
            tier_rect = tier_surf.get_rect(topleft=(rect.x + 6, rect.y + 6))
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
                self.render_equipment_tooltip(equipment, mouse_pos, character, from_inventory=True)
                return

        # Regular material tooltip
        mat = item_stack.get_material()
        if not mat:
            return

        tw, th, pad = 250, 120, 10
        x, y = mouse_pos[0] + 15, mouse_pos[1] + 15
        if x + tw > Config.SCREEN_WIDTH:
            x = mouse_pos[0] - tw - 15
        if y + th > Config.SCREEN_HEIGHT:
            y = mouse_pos[1] - th - 15

        surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        surf.fill(Config.COLOR_TOOLTIP_BG)

        y_pos = pad
        color = Config.RARITY_COLORS.get(mat.rarity, (200, 200, 200))
        surf.blit(self.font.render(mat.name, True, color), (pad, y_pos))
        y_pos += 25
        surf.blit(self.small_font.render(f"Tier {mat.tier} | {mat.category.capitalize()}", True, (180, 180, 180)),
                  (pad, y_pos))
        y_pos += 20
        surf.blit(self.small_font.render(f"Rarity: {mat.rarity.capitalize()}", True, color), (pad, y_pos))

        self.screen.blit(surf, (x, y))

    def render_crafting_ui(self, character: Character, mouse_pos: Tuple[int, int], selected_recipe=None, user_placement=None):
        """
        Render crafting UI with two-panel layout:
        - Left panel (450px): Recipe list
        - Right panel (700px): Placement visualization + craft buttons

        Args:
            selected_recipe: Currently selected recipe (to highlight in UI)
            user_placement: User's current material placement (Dict[str, str])
        """
        if user_placement is None:
            user_placement = {}
        if not character.crafting_ui_open or not character.active_station:
            return None

        # Store these temporarily so child methods can access them
        # (Python scoping doesn't allow nested functions to see parameters)
        self._temp_selected_recipe = selected_recipe
        self._temp_user_placement = user_placement

        # Always render recipe list on the left (pass scroll offset from game engine)
        # Note: Renderer doesn't have direct access to game engine, so we need to get it via a hack
        # Check if there's a scroll offset to use (this will be set by the caller)
        scroll_offset = getattr(self, '_temp_scroll_offset', 0)
        recipe_result = self._render_recipe_selection_sidebar(character, mouse_pos, scroll_offset)

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
        surf.blit(self.small_font.render("[ESC] Close | Select recipe to place materials", True, (180, 180, 180)), (ww - s(400), s(20)))

        # Get recipes for this station
        recipes = recipe_db.get_recipes_for_station(character.active_station.station_type.value,
                                                    character.active_station.tier)

        # ======================
        # LEFT PANEL: Recipe List with Scrolling
        # ======================
        visible_recipes = []  # Initialize to empty list
        if not recipes:
            surf.blit(self.font.render("No recipes available", True, (200, 200, 200)), (s(20), s(80)))
        else:
            # Apply scroll offset and show 8 recipes at a time
            total_recipes = len(recipes)
            max_visible = 8
            start_idx = min(scroll_offset, max(0, total_recipes - max_visible))
            end_idx = min(start_idx + max_visible, total_recipes)
            visible_recipes = recipes[start_idx:end_idx]

            # Show scroll indicators if needed
            if total_recipes > max_visible:
                scroll_text = f"Recipes {start_idx + 1}-{end_idx} of {total_recipes}"
                scroll_surf = self.small_font.render(scroll_text, True, (150, 150, 150))
                surf.blit(scroll_surf, (s(20), s(50)))

                # Show scroll arrows
                if start_idx > 0:
                    up_arrow = self.small_font.render("▲ Scroll Up", True, (100, 200, 100))
                    surf.blit(up_arrow, (left_panel_w - s(120), s(50)))
                if end_idx < total_recipes:
                    down_arrow = self.small_font.render("▼ Scroll Down", True, (100, 200, 100))
                    surf.blit(down_arrow, (left_panel_w - s(120), wh - s(30)))

            y_off = s(70)
            for i, recipe in enumerate(visible_recipes):
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

                # Material requirements (compact)
                req_y = btn.y + s(30)
                for inp in recipe.inputs:
                    mat_id = inp.get('materialId', '')
                    req = inp.get('quantity', 0)
                    avail = character.inventory.get_item_count(mat_id)
                    mat = mat_db.get_material(mat_id)
                    mat_name = mat.name if mat else mat_id
                    req_color = (100, 255, 100) if avail >= req or Config.DEBUG_INFINITE_RESOURCES else (255, 100, 100)
                    surf.blit(self.small_font.render(f"{mat_name}: {avail}/{req}", True, req_color),
                              (btn.x + s(15), req_y))
                    req_y += s(16)

                y_off += btn_height + s(8)

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

            # Placement visualization area
            placement_h = s(380)
            placement_rect = pygame.Rect(right_panel_x, right_panel_y, right_panel_w - s(40), placement_h)
            pygame.draw.rect(surf, (30, 30, 40), placement_rect)
            pygame.draw.rect(surf, (80, 80, 90), placement_rect, 2)

            # Render discipline-specific placement UI
            station_type = character.active_station.station_type.value
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

            # Craft buttons at bottom of right panel
            if can_craft:
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
        return pygame.Rect(wx, wy, ww, wh), return_recipes, grid_rects_absolute

    def render_equipment_ui(self, character: Character, mouse_pos: Tuple[int, int]):
        if not character.equipment_ui_open:
            return None

        ww, wh = Config.MENU_MEDIUM_W, Config.MENU_MEDIUM_H
        wx = Config.VIEWPORT_WIDTH - ww - Config.scale(20)  # Right-aligned with margin
        wy = Config.scale(50)

        surf = pygame.Surface((ww, wh), pygame.SRCALPHA)
        surf.fill((20, 20, 30, 240))

        surf.blit(self.font.render("EQUIPMENT", True, (255, 215, 0)), (Config.scale(20), Config.scale(20)))
        surf.blit(self.small_font.render("[E or ESC] Close | [SHIFT+CLICK] to unequip", True, (180, 180, 180)),
                  (ww - Config.scale(350), Config.scale(20)))

        slot_size = Config.scale(80)
        s = Config.scale  # Shorthand for readability
        slots_layout = {
            'helmet': (ww // 2 - slot_size // 2, s(70)),
            'mainHand': (ww // 2 - slot_size - s(20), s(170)),
            'chestplate': (ww // 2 - slot_size // 2, s(170)),
            'offHand': (ww // 2 + s(20), s(170)),
            'gauntlets': (ww // 2 - slot_size - s(20), s(270)),
            'leggings': (ww // 2 - slot_size // 2, s(270)),
            'boots': (ww // 2 - slot_size // 2, s(370)),
            'accessory': (ww // 2 + s(20), s(270)),
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
                inner_rect = pygame.Rect(sx + s(5), sy + s(5), slot_size - s(10), slot_size - s(10))
                pygame.draw.rect(surf, rarity_color, inner_rect)

                tier_text = f"T{item.tier}"
                tier_surf = self.small_font.render(tier_text, True, (0, 0, 0))
                surf.blit(tier_surf, (sx + s(8), sy + s(8)))

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

        if hovered_slot:
            slot_name, item = hovered_slot
            self.render_equipment_tooltip(item, (mouse_pos[0], mouse_pos[1]), character, from_inventory=False)

        self.screen.blit(surf, (wx, wy))
        return pygame.Rect(wx, wy, ww, wh), equipment_rects

    def render_equipment_tooltip(self, item: EquipmentItem, mouse_pos: Tuple[int, int], character: Character,
                                 from_inventory: bool = False):
        s = Config.scale
        tw, th, pad = s(320), s(340), s(10)  # Increased height for enchantments
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

        dur_pct = (item.durability_current / item.durability_max) * 100
        dur_color = (100, 255, 100) if dur_pct > 50 else (255, 200, 100) if dur_pct > 25 else (255, 100, 100)
        dur_text = f"Durability: {item.durability_current}/{item.durability_max} ({dur_pct:.0f}%)"
        if Config.DEBUG_INFINITE_RESOURCES:
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

    def render_enchantment_selection_ui(self, mouse_pos: Tuple[int, int], recipe: Recipe, compatible_items: List):
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
        surf.blit(self.small_font.render("[ESC] Cancel | [CLICK] Select Item", True, (180, 180, 180)),
                  (ww - 280, 20))

        # Description
        y_pos = 60
        surf.blit(self.small_font.render("Select an item to enchant:", True, (200, 200, 200)), (20, y_pos))
        y_pos += 30

        # List compatible items
        slot_size = 60
        item_rects = []

        for idx, (source_type, source_id, item_stack, equipment) in enumerate(compatible_items):
            if y_pos + slot_size + 10 > wh - 20:
                break  # Don't overflow window

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
        """Render the start menu with New World / Load World / Temporary World options"""
        s = Config.scale
        # Menu dimensions
        ww, wh = Config.MENU_SMALL_W, Config.MENU_SMALL_H
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
            ("Temporary World", "Practice mode (no saves)")
        ]

        button_rects = []
        y_offset = s(150)
        button_height = s(80)

        for idx, (option_name, option_desc) in enumerate(options):
            button_rect = pygame.Rect(s(50), y_offset + idx * (button_height + s(20)), ww - s(100), button_height)

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

            name_surf = self.font.render(class_def.name, True, (255, 215, 0))
            surf.blit(name_surf, (x + s(10), y + s(8)))

            bonus_y = y + s(35)
            for bonus_type, value in list(class_def.bonuses.items())[:2]:
                bonus_text = f"+{value if isinstance(value, int) else f'{value * 100:.0f}%'} {bonus_type.replace('_', ' ')}"
                bonus_surf = self.tiny_font.render(bonus_text, True, (100, 200, 100))
                surf.blit(bonus_surf, (x + s(15), bonus_y))
                bonus_y += s(14)

            if is_hovered:
                select_surf = self.small_font.render("[CLICK] Select", True, (100, 255, 100))
                surf.blit(select_surf, (x + col_width - select_surf.get_width() - s(10), y + card_height - s(25)))

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

    def render_text(self, text: str, x: int, y: int, bold: bool = False, small: bool = False):
        font = self.small_font if small else self.font
        if bold:
            font.set_bold(True)
        surf = font.render(text, True, Config.COLOR_TEXT)
        self.screen.blit(surf, (x, y))
        if bold:
            font.set_bold(False)
