# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification file for Game-1

This file defines how the game is packaged into a standalone executable.
Run with: pyinstaller Game1.spec

Author: Auto-generated for Game-1 packaging
"""

from PyInstaller.utils.hooks import collect_data_files
import os

# Get the base directory
block_cipher = None
base_dir = os.path.abspath(os.getcwd())

# Define all data files and directories to include
# Format: (source_path, destination_folder_in_bundle)
added_files = [
    # Asset directory (358 MB of images)
    ('assets', 'assets'),

    # JSON data directories
    ('items.JSON', 'items.JSON'),
    ('recipes.JSON', 'recipes.JSON'),
    ('placements.JSON', 'placements.JSON'),
    ('Definitions.JSON', 'Definitions.JSON'),
    ('progression', 'progression'),
    ('Skills', 'Skills'),

    # Note: saves/ directory will be created in user's home directory
    # to ensure write permissions (handled in code)
]

# Analysis: Find all Python files and dependencies
a = Analysis(
    ['main.py'],
    pathex=[base_dir],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        # Explicitly include all game modules
        'core',
        'core.game_engine',
        'core.config',
        'core.camera',
        'core.notifications',
        'core.testing',
        'data',
        'data.models',
        'data.databases',
        'entities',
        'entities.character',
        'entities.components',
        'systems',
        'rendering',
        'rendering.renderer',
        'rendering.image_cache',
        'Combat',
        'Combat.combat_manager',
        'Combat.enemy',
        'Crafting-subdisciplines',
        # Pygame modules
        'pygame',
        'pygame.mixer',
        'pygame.font',
        'pygame.image',
        'pygame.display',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude development tools to reduce size
        'pytest',
        'IPython',
        'black',
        'mypy',
        'flake8',
        # Exclude unnecessary stdlib modules
        'tkinter',
        'unittest',
        'pydoc',
        'doctest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PYZ: Create Python archive
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# EXE: Create executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Game1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress with UPX (reduces size by ~30%)
    console=False,  # No console window (set True for debugging)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # Uncomment when you have an icon
)

# COLLECT: Bundle everything together
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Game1',
)

# Notes:
# - Output will be in dist/Game1/
# - Directory contains the executable and all data files
# - Total size: ~360-400 MB
# - First run may be slow (asset loading)
# - Save files will be in user's home directory for cross-platform compatibility
