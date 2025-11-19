"""Camera system for viewport"""

from data.models.world import Position
from .config import Config


class Camera:
    """Camera/viewport system that follows the player"""

    def __init__(self):
        self.position = Position(0, 0)

    def follow(self, target_pos: Position):
        """Center camera on target position"""
        self.position.x = target_pos.x
        self.position.y = target_pos.y

    def world_to_screen(self, world_pos: Position) -> tuple:
        """Convert world coordinates to screen coordinates"""
        screen_x = (world_pos.x - self.position.x) * Config.TILE_SIZE + Config.VIEWPORT_WIDTH // 2
        screen_y = (world_pos.y - self.position.y) * Config.TILE_SIZE + Config.VIEWPORT_HEIGHT // 2
        return (screen_x, screen_y)
