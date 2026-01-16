"""Camera system for viewport"""

from typing import Tuple
from data.models.world import Position
from .config import Config


class Camera:
    """Camera/viewport system that follows the player"""

    def __init__(self, viewport_width: int, viewport_height: int):
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.position = Position(0, 0, 0)

    def follow(self, target: Position):
        """Center camera on target position"""
        self.position = target.copy()

    def world_to_screen(self, world_pos: Position) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates"""
        sx = (world_pos.x - self.position.x) * Config.TILE_SIZE + self.viewport_width // 2
        sy = (world_pos.y - self.position.y) * Config.TILE_SIZE + self.viewport_height // 2
        return int(sx), int(sy)

    def screen_to_world(self, screen_x: int, screen_y: int) -> Position:
        """Convert screen coordinates to world coordinates"""
        world_x = (screen_x - self.viewport_width // 2) / Config.TILE_SIZE + self.position.x
        world_y = (screen_y - self.viewport_height // 2) / Config.TILE_SIZE + self.position.y
        return Position(world_x, world_y, self.position.z)
