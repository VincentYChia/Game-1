"""
Path Management for Packaged and Development Environments

Handles resource and save file paths correctly whether running:
- From source (python main.py)
- From PyInstaller bundle (dist/Game1/Game1.exe)
"""

import sys
import os
from pathlib import Path
from typing import Union


class PathManager:
    """Manages file paths for both development and packaged environments."""

    _instance = None
    _initialized = False

    def __new__(cls):
        """Singleton pattern - only one PathManager instance."""
        if cls._instance is None:
            cls._instance = super(PathManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize path manager (only runs once due to singleton)."""
        if not PathManager._initialized:
            self._setup_paths()
            PathManager._initialized = True

    def _setup_paths(self):
        """Determine base paths for resources and saves."""
        # Determine if we're running as a PyInstaller bundle
        self.is_bundled = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

        if self.is_bundled:
            # Running as packaged executable
            # sys._MEIPASS is the temporary folder PyInstaller extracts files to
            self.base_path = Path(sys._MEIPASS)
            # Use user's home directory for saves (writable location)
            self.save_path = self._get_user_data_directory() / "saves"
        else:
            # Running from source
            # Base path is the directory containing main.py
            self.base_path = Path(__file__).parent.parent.resolve()
            # Saves in the same directory as source
            self.save_path = self.base_path / "saves"

        # Ensure save directory exists
        self.save_path.mkdir(parents=True, exist_ok=True)

        # Debug info (useful for troubleshooting)
        self._log_paths()

    def _get_user_data_directory(self) -> Path:
        """
        Get platform-specific user data directory.

        Returns:
            Path to user data directory:
            - Windows: %APPDATA%/Game1
            - Linux: ~/.local/share/Game1
            - macOS: ~/Library/Application Support/Game1
        """
        if sys.platform == 'win32':
            # Windows: C:\Users\<username>\AppData\Roaming\Game1
            base = Path(os.getenv('APPDATA', '~'))
            return base / 'Game1'
        elif sys.platform == 'darwin':
            # macOS: ~/Library/Application Support/Game1
            return Path.home() / 'Library' / 'Application Support' / 'Game1'
        else:
            # Linux: ~/.local/share/Game1
            return Path.home() / '.local' / 'share' / 'Game1'

    def _log_paths(self):
        """Log path configuration for debugging."""
        print(f"[PathManager] Bundled: {self.is_bundled}")
        print(f"[PathManager] Base path: {self.base_path}")
        print(f"[PathManager] Save path: {self.save_path}")

    def get_resource_path(self, relative_path: Union[str, Path]) -> Path:
        """
        Get absolute path to a resource file.

        Args:
            relative_path: Path relative to game root (e.g., 'assets/enemies/slime.png')

        Returns:
            Absolute path to the resource
        """
        return self.base_path / relative_path

    def get_save_path(self, filename: str = None) -> Path:
        """
        Get path to save directory or specific save file.

        Args:
            filename: Optional save filename (e.g., 'autosave.json')

        Returns:
            Path to save directory or specific save file
        """
        if filename:
            return self.save_path / filename
        return self.save_path

    def resource_exists(self, relative_path: Union[str, Path]) -> bool:
        """
        Check if a resource file exists.

        Args:
            relative_path: Path relative to game root

        Returns:
            True if resource exists
        """
        return self.get_resource_path(relative_path).exists()


# Global singleton instance
_path_manager = PathManager()


# Convenience functions for easy access
def get_resource_path(relative_path: Union[str, Path]) -> Path:
    """Get absolute path to a resource file."""
    return _path_manager.get_resource_path(relative_path)


def get_save_path(filename: str = None) -> Path:
    """Get path to save directory or specific save file."""
    return _path_manager.get_save_path(filename)


def resource_exists(relative_path: Union[str, Path]) -> bool:
    """Check if a resource file exists."""
    return _path_manager.resource_exists(relative_path)


def is_bundled() -> bool:
    """Check if running as packaged executable."""
    return _path_manager.is_bundled
