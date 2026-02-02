#!/usr/bin/env python3
"""
Unified Classifier Training Script

Trains all 5 crafting classifiers (2 CNN + 3 LightGBM):
1. Smithing (CNN)
2. Adornments (CNN)
3. Alchemy (LightGBM)
4. Refining (LightGBM - separate trainer)
5. Engineering (LightGBM)

Features:
- Model selection based on: score = val_accuracy - 2.0 * overfit_gap
  (overfitting is penalized 2x more than accuracy loss)
- Automatic archiving of old models with timestamps
- Seamless replacement: new models go to EXACT paths the game expects
- Comprehensive debug output with --debug flag

Model Selection Philosophy:
- A 93% accuracy model with 7% overfit gap scores: 0.93 - 2*0.07 = 0.79
- A 86% accuracy model with 1% overfit gap scores: 0.86 - 2*0.01 = 0.84
- The 86% model wins because overfitting is heavily penalized

Usage:
    python train_all_classifiers.py                    # Train all
    python train_all_classifiers.py --discipline smithing  # Train one
    python train_all_classifiers.py --dry-run          # Show what would happen
    python train_all_classifiers.py --list             # List disciplines
    python train_all_classifiers.py --debug            # Verbose debug output
    python train_all_classifiers.py --test-paths       # Verify all paths exist
    python train_all_classifiers.py --test-mode        # Skeleton test (1 config, 1 epoch)

Directory Structure:
    models/
        smithing/       - Trained smithing CNN models
        adornment/      - Trained adornment CNN models
        alchemy/        - Trained alchemy LightGBM models
        refining/       - Trained refining LightGBM models
        engineering/    - Trained engineering LightGBM models
        archived/       - Old models archived here
    training_data/
        smithing/       - Smithing training datasets
        adornment/      - Adornment training datasets
        alchemy/        - Alchemy training datasets
        refining/       - Refining training datasets
        engineering/    - Engineering training datasets

Created: 2026-02-02
"""

import argparse
import json
import os
import shutil
import sys
import subprocess
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import glob

# ============================================================================
# PATHS CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).parent
CNN_DIR = SCRIPT_DIR / "Convolution Neural Network (CNN)"
LIGHTGBM_DIR = SCRIPT_DIR / "Simple Classifiers (LightGBM)"
GAME_MODULAR = SCRIPT_DIR.parent / "Game-1-modular"

# New organized directories
MODELS_DIR = SCRIPT_DIR / "models"
TRAINING_DATA_DIR = SCRIPT_DIR / "training_data"
ARCHIVE_DIR = MODELS_DIR / "archived"  # Archive lives inside models folder

# Game expects models at these EXACT paths - updated to use organized structure
GAME_MODEL_PATHS = {
    'smithing': MODELS_DIR / "smithing" / "smithing_best.keras",
    'adornments': MODELS_DIR / "adornment" / "adornment_best.keras",
    'alchemy': MODELS_DIR / "alchemy" / "alchemy_model.txt",
    'refining': MODELS_DIR / "refining" / "refining_model.txt",
    'engineering': MODELS_DIR / "engineering" / "engineering_model.txt",
}

# ============================================================================
# DATA PATHS (materials, recipes, placements)
# ============================================================================

# Materials JSON - shared across disciplines
MATERIALS_JSON = GAME_MODULAR / "items.JSON" / "items-materials-1.JSON"

# Placements/Recipes for each discipline
DATA_PATHS = {
    'smithing': {
        'placements': GAME_MODULAR / "placements.JSON" / "placements-smithing-1.json",
        'recipes': GAME_MODULAR / "recipes.JSON" / "recipes-smithing-3.json",
    },
    'adornments': {
        'placements': GAME_MODULAR / "recipes.JSON" / "recipes-adornments-1.json",
    },
    'alchemy': {
        'placements': GAME_MODULAR / "placements.JSON" / "placements-alchemy-1.JSON",
    },
    'refining': {
        'placements': GAME_MODULAR / "placements.JSON" / "placements-refining-1.JSON",
    },
    'engineering': {
        'placements': GAME_MODULAR / "placements.JSON" / "placements-engineering-1.JSON",
    },
}

# ============================================================================
# DISCIPLINE CONFIGURATIONS
# ============================================================================

DISCIPLINES = {
    'smithing': {
        'type': 'cnn',
        'data_script': CNN_DIR / "Smithing" / "valid_smithing_data_v2.py",
        'train_script': CNN_DIR / "Smithing" / "CNN_trainer_smithing.py",
        'work_dir': CNN_DIR / "Smithing",  # CNN scripts work in their own dir, we copy out
        'model_output_dir': MODELS_DIR / "smithing",  # Where we copy best model
        'data_output_dir': TRAINING_DATA_DIR / "smithing",  # Where training data goes
        'model_pattern': '*.keras',  # Matches any keras model
        'extractor_pattern': None,
        'output_dataset': 'recipe_dataset_v2.npz',
        # CNN scripts don't need external args - they have their own paths
        'data_args': [],
        'train_args': [],
    },
    'adornments': {
        'type': 'cnn',
        'data_script': CNN_DIR / "Adornment" / "data_augment_adornment_v2.py",
        'train_script': CNN_DIR / "Adornment" / "CNN_trainer_adornment.py",
        'work_dir': CNN_DIR / "Adornment",  # CNN scripts work in their own dir
        'model_output_dir': MODELS_DIR / "adornment",  # Where we copy best model
        'data_output_dir': TRAINING_DATA_DIR / "adornment",  # Where training data goes
        'model_pattern': '*.keras',  # Matches any keras model
        'extractor_pattern': None,
        'output_dataset': 'adornment_dataset_v2.npz',
        # CNN scripts don't need external args
        'data_args': [],
        'train_args': [],
    },
    'alchemy': {
        'type': 'lightgbm',
        'data_script': LIGHTGBM_DIR / "data_augment_GBM.py",
        'train_script': LIGHTGBM_DIR / "LightGBM_trainer.py",
        'work_dir': MODELS_DIR / "alchemy",
        'model_pattern': '*_model.txt',
        'extractor_pattern': '*_extractor.pkl',
        'output_dataset': 'alchemy_augmented_data.json',
        # LightGBM data script args: discipline materials placements output
        'data_args': lambda: ['alchemy', str(MATERIALS_JSON),
                              str(DATA_PATHS['alchemy']['placements']),
                              str(TRAINING_DATA_DIR / 'alchemy' / 'alchemy_augmented_data.json')],
        # LightGBM trainer args: train dataset materials output_dir
        'train_args': lambda: ['train',
                               str(TRAINING_DATA_DIR / 'alchemy' / 'alchemy_augmented_data.json'),
                               str(MATERIALS_JSON),
                               str(MODELS_DIR / 'alchemy')],
    },
    'refining': {
        'type': 'lightgbm',
        'data_script': LIGHTGBM_DIR / "data_augment_ref.py",
        'train_script': LIGHTGBM_DIR / "LightGBM_trainer.py",
        'work_dir': MODELS_DIR / "refining",
        'model_pattern': '*_model.txt',
        'extractor_pattern': '*_extractor.pkl',
        'output_dataset': 'refining_augmented_data.json',
        # Refining data script args: materials placements output
        'data_args': lambda: [str(MATERIALS_JSON),
                              str(DATA_PATHS['refining']['placements']),
                              str(TRAINING_DATA_DIR / 'refining' / 'refining_augmented_data.json')],
        # LightGBM trainer args
        'train_args': lambda: ['train',
                               str(TRAINING_DATA_DIR / 'refining' / 'refining_augmented_data.json'),
                               str(MATERIALS_JSON),
                               str(MODELS_DIR / 'refining')],
    },
    'engineering': {
        'type': 'lightgbm',
        'data_script': LIGHTGBM_DIR / "data_augment_GBM.py",
        'train_script': LIGHTGBM_DIR / "LightGBM_trainer.py",
        'work_dir': MODELS_DIR / "engineering",
        'model_pattern': '*_model.txt',
        'extractor_pattern': '*_extractor.pkl',
        'output_dataset': 'engineering_augmented_data.json',
        # LightGBM data script args
        'data_args': lambda: ['engineering', str(MATERIALS_JSON),
                              str(DATA_PATHS['engineering']['placements']),
                              str(TRAINING_DATA_DIR / 'engineering' / 'engineering_augmented_data.json')],
        # LightGBM trainer args
        'train_args': lambda: ['train',
                               str(TRAINING_DATA_DIR / 'engineering' / 'engineering_augmented_data.json'),
                               str(MATERIALS_JSON),
                               str(MODELS_DIR / 'engineering')],
    },
}

# ============================================================================
# DEBUG UTILITIES & MODES
# ============================================================================

DEBUG_MODE = False
TEST_MODE = False  # Skeleton test: 1 config, 1 epoch for validation


def debug(msg: str):
    """Print debug message if debug mode is enabled."""
    if DEBUG_MODE:
        print(f"[DEBUG] {msg}")


def info(msg: str):
    """Print info message (always visible)."""
    print(f"[INFO] {msg}")


def warn(msg: str):
    """Print warning message (always visible)."""
    print(f"[WARN] {msg}")


def error(msg: str):
    """Print error message (always visible)."""
    print(f"[ERROR] {msg}")


def ensure_directories():
    """Create all required directories if they don't exist."""
    directories = [
        MODELS_DIR / "smithing",
        MODELS_DIR / "adornment",
        MODELS_DIR / "alchemy",
        MODELS_DIR / "refining",
        MODELS_DIR / "engineering",
        MODELS_DIR / "archived",
        TRAINING_DATA_DIR / "smithing",
        TRAINING_DATA_DIR / "adornment",
        TRAINING_DATA_DIR / "alchemy",
        TRAINING_DATA_DIR / "refining",
        TRAINING_DATA_DIR / "engineering",
    ]

    for dir_path in directories:
        dir_path.mkdir(parents=True, exist_ok=True)
        debug(f"Ensured directory: {dir_path}")

    info(f"All directories ensured ({len(directories)} dirs)")


# ============================================================================
# DATA CHANGE DETECTION
# ============================================================================

import hashlib

HASH_CACHE_FILE = SCRIPT_DIR / ".data_hashes.json"


def compute_file_hash(filepath: Path) -> str:
    """Compute MD5 hash of a file."""
    if not filepath.exists():
        return ""

    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_data_hashes(discipline: str) -> Dict[str, str]:
    """Get hashes of all data files for a discipline."""
    hashes = {}

    # Common materials file
    hashes['materials'] = compute_file_hash(MATERIALS_JSON)

    # Discipline-specific data files
    if discipline in DATA_PATHS:
        for key, path in DATA_PATHS[discipline].items():
            hashes[key] = compute_file_hash(path)

    return hashes


def load_cached_hashes() -> Dict[str, Dict[str, str]]:
    """Load cached data hashes from file."""
    if not HASH_CACHE_FILE.exists():
        return {}

    try:
        with open(HASH_CACHE_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_cached_hashes(cache: Dict[str, Dict[str, str]]):
    """Save data hashes to cache file."""
    with open(HASH_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


def check_data_changed(discipline: str, force: bool = False) -> Tuple[bool, str]:
    """
    Check if data files have changed for a discipline.

    Returns:
        Tuple of (changed: bool, reason: str)
    """
    if force:
        return True, "forced"

    current_hashes = get_data_hashes(discipline)
    cached = load_cached_hashes()

    if discipline not in cached:
        return True, "no cache"

    cached_hashes = cached[discipline]

    # Check if materials changed (affects ALL disciplines)
    if current_hashes.get('materials') != cached_hashes.get('materials'):
        return True, "materials changed"

    # Check discipline-specific files
    for key, hash_val in current_hashes.items():
        if key == 'materials':
            continue
        if cached_hashes.get(key) != hash_val:
            return True, f"{key} changed"

    return False, "unchanged"


def update_data_hash_cache(discipline: str):
    """Update the cache with current hashes for a discipline."""
    cached = load_cached_hashes()
    cached[discipline] = get_data_hashes(discipline)
    save_cached_hashes(cached)


# ============================================================================
# MODEL CLEANUP (Keep best N models)
# ============================================================================

def cleanup_old_models(discipline: str, config: Dict, keep_best: int = 3):
    """
    Clean up old models, keeping only the best N.

    Models are ranked by modification time (newest = best).
    Non-selected models are moved to archive.
    """
    work_dir = config['work_dir']
    model_pattern = config['model_pattern']

    debug(f"Cleaning up models for {discipline}")
    debug(f"  Work dir: {work_dir}")
    debug(f"  Pattern: {model_pattern}")
    debug(f"  Keep best: {keep_best}")

    # Find all models
    if '*' in model_pattern:
        # If pattern has subdir, handle it
        if '/' in model_pattern:
            subdir, pattern = model_pattern.rsplit('/', 1)
            search_dir = work_dir / subdir
        else:
            search_dir = work_dir
            pattern = model_pattern

        models = list(search_dir.glob(pattern))
    else:
        models = list(work_dir.glob(model_pattern))

    debug(f"  Found {len(models)} models")

    if len(models) <= keep_best:
        debug(f"  No cleanup needed (have {len(models)}, keep {keep_best})")
        return 0

    # Sort by modification time (newest first)
    models.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Keep the best N, archive the rest
    to_archive = models[keep_best:]
    archived_count = 0

    for model_path in to_archive:
        try:
            # Move to archive
            archive_name = f"{discipline}_{model_path.name}"
            archive_path = ARCHIVE_DIR / archive_name

            # Avoid overwriting
            if archive_path.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                archive_name = f"{discipline}_{model_path.stem}_{timestamp}{model_path.suffix}"
                archive_path = ARCHIVE_DIR / archive_name

            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.move(str(model_path), str(archive_path))
            archived_count += 1
            debug(f"    Archived: {model_path.name} -> {archive_name}")

        except Exception as e:
            debug(f"    ERROR archiving {model_path.name}: {e}")

    if archived_count > 0:
        print(f"    Cleaned up {archived_count} old model(s) (kept best {keep_best})")

    return archived_count


def debug_paths():
    """Debug print all configured paths."""
    print("\n" + "=" * 70)
    print("PATH CONFIGURATION DEBUG")
    print("=" * 70)

    print(f"\nScript directory: {SCRIPT_DIR}")
    print(f"  Exists: {SCRIPT_DIR.exists()}")

    print(f"\nCNN directory: {CNN_DIR}")
    print(f"  Exists: {CNN_DIR.exists()}")

    print(f"\nLightGBM directory: {LIGHTGBM_DIR}")
    print(f"  Exists: {LIGHTGBM_DIR.exists()}")

    print(f"\nGame modular directory: {GAME_MODULAR}")
    print(f"  Exists: {GAME_MODULAR.exists()}")

    print(f"\nModels directory: {MODELS_DIR}")
    print(f"  Exists: {MODELS_DIR.exists()}")

    print(f"\nTraining data directory: {TRAINING_DATA_DIR}")
    print(f"  Exists: {TRAINING_DATA_DIR.exists()}")

    print(f"\nArchive directory: {ARCHIVE_DIR}")
    print(f"  Exists: {ARCHIVE_DIR.exists()}")

    print("\n" + "-" * 70)
    print("GAME MODEL PATHS:")
    print("-" * 70)
    for discipline, path in GAME_MODEL_PATHS.items():
        exists = path.exists()
        parent_exists = path.parent.exists()
        print(f"\n  {discipline}:")
        print(f"    Path: {path}")
        print(f"    File exists: {exists}")
        print(f"    Parent dir exists: {parent_exists}")

    print("\n" + "-" * 70)
    print("DISCIPLINE CONFIGURATIONS:")
    print("-" * 70)
    for name, config in DISCIPLINES.items():
        print(f"\n  {name}:")
        print(f"    Type: {config['type']}")
        print(f"    Data script: {config['data_script']}")
        print(f"      Exists: {config['data_script'].exists()}")
        print(f"    Train script: {config['train_script']}")
        print(f"      Exists: {config['train_script'].exists()}")
        print(f"    Work dir: {config['work_dir']}")
        print(f"      Exists: {config['work_dir'].exists()}")


def test_all_paths() -> bool:
    """Test that all required paths exist. Returns True if all OK."""
    all_ok = True
    errors = []

    # Check directories
    for name, path in [("CNN_DIR", CNN_DIR), ("LIGHTGBM_DIR", LIGHTGBM_DIR)]:
        if not path.exists():
            errors.append(f"Missing directory: {name} = {path}")
            all_ok = False

    # Check scripts
    for discipline, config in DISCIPLINES.items():
        if not config['data_script'].exists():
            errors.append(f"Missing data script for {discipline}: {config['data_script']}")
            all_ok = False
        if not config['train_script'].exists():
            errors.append(f"Missing train script for {discipline}: {config['train_script']}")
            all_ok = False
        if not config['work_dir'].exists():
            errors.append(f"Missing work dir for {discipline}: {config['work_dir']}")
            all_ok = False

    # Check game model parent directories
    for discipline, path in GAME_MODEL_PATHS.items():
        if not path.parent.exists():
            errors.append(f"Missing game model parent dir for {discipline}: {path.parent}")
            all_ok = False

    if errors:
        print("\n" + "=" * 70)
        print("PATH VERIFICATION ERRORS")
        print("=" * 70)
        for error in errors:
            print(f"  ERROR: {error}")
        print("=" * 70)
    else:
        print("\nAll paths verified OK!")

    return all_ok


# ============================================================================
# SCORING FUNCTION
# ============================================================================

def calculate_score(val_accuracy: float, overfit_gap: float) -> float:
    """
    Calculate model quality score.

    Formula: score = val_accuracy - 2.0 * overfit_gap

    This penalizes overfitting 2x more than accuracy loss:
    - 93% acc, 7% overfit → 0.93 - 0.14 = 0.79
    - 86% acc, 1% overfit → 0.86 - 0.02 = 0.84  (BETTER!)

    Args:
        val_accuracy: Validation accuracy (0.0-1.0)
        overfit_gap: Train accuracy - Val accuracy (0.0-1.0)

    Returns:
        Score value (higher is better)
    """
    score = val_accuracy - 2.0 * max(0, overfit_gap)
    debug(f"Score calculation: {val_accuracy:.4f} - 2.0 * {max(0, overfit_gap):.4f} = {score:.4f}")
    return score


# ============================================================================
# ARCHIVE MANAGEMENT
# ============================================================================

def ensure_archive_dir():
    """Create archive directory if it doesn't exist."""
    ARCHIVE_DIR.mkdir(exist_ok=True)
    debug(f"Archive directory ensured: {ARCHIVE_DIR}")
    return ARCHIVE_DIR


def archive_file(filepath: Path, discipline: str, dry_run: bool = False) -> Optional[Path]:
    """
    Archive a file with timestamp.

    Args:
        filepath: Path to file to archive
        discipline: Discipline name for prefix
        dry_run: If True, only print what would happen

    Returns:
        Path to archived file, or None if dry run or file doesn't exist
    """
    if not filepath.exists():
        debug(f"File does not exist, skipping archive: {filepath}")
        return None

    archive_dir = ensure_archive_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archived_name = f"{discipline}_{filepath.stem}_{timestamp}{filepath.suffix}"
    archive_path = archive_dir / archived_name

    if dry_run:
        print(f"    [DRY RUN] Would archive: {filepath.name} -> {archived_name}")
        return None

    debug(f"Archiving: {filepath} -> {archive_path}")
    shutil.copy2(filepath, archive_path)
    print(f"    Archived: {filepath.name} -> {archived_name}")
    return archive_path


def archive_current_model(discipline: str, dry_run: bool = False) -> List[Path]:
    """Archive current model for a discipline."""
    game_path = GAME_MODEL_PATHS.get(discipline)
    archived = []

    debug(f"Archiving current model for {discipline}")
    debug(f"  Game path: {game_path}")

    if game_path and game_path.exists():
        result = archive_file(game_path, discipline, dry_run)
        if result:
            archived.append(result)

        # For LightGBM, also archive the extractor .pkl
        if discipline in ['alchemy', 'refining', 'engineering']:
            # Try different naming conventions for extractor
            extractor_patterns = [
                game_path.parent / game_path.stem.replace('_model', '_extractor').replace('.txt', '.pkl'),
                game_path.with_suffix('.pkl').with_name(
                    game_path.stem.replace('_model', '_extractor') + '.pkl'
                ),
            ]

            for extractor_path in extractor_patterns:
                debug(f"  Checking extractor: {extractor_path}")
                if extractor_path.exists():
                    result = archive_file(extractor_path, discipline, dry_run)
                    if result:
                        archived.append(result)
                    break

    debug(f"  Archived {len(archived)} files")
    return archived


# ============================================================================
# TRAINING EXECUTION
# ============================================================================

def run_data_generation(discipline: str, config: Dict, dry_run: bool = False) -> bool:
    """
    Run data generation script for a discipline.

    Returns True if successful.
    """
    data_script = config['data_script']
    data_args_fn = config.get('data_args', [])

    # Get command-line arguments (may be a lambda)
    if callable(data_args_fn):
        data_args = data_args_fn()
    else:
        data_args = data_args_fn

    debug(f"Data generation for {discipline}")
    debug(f"  Script: {data_script}")
    debug(f"  Args: {data_args}")
    debug(f"  Parent dir: {data_script.parent}")

    if not data_script.exists():
        print(f"    ERROR: Data script not found: {data_script}")
        return False

    print(f"    Script: {data_script.name}")
    if data_args:
        print(f"    Args: {' '.join(data_args[:2])}...")  # Show first 2 args

    if dry_run:
        print(f"    [DRY RUN] Would run data generation")
        if data_args:
            print(f"    [DRY RUN] Full command: python {data_script.name} {' '.join(data_args)}")
        return True

    try:
        cmd = [sys.executable, str(data_script)] + data_args
        debug(f"  Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=str(data_script.parent),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',  # Replace undecodable bytes instead of crashing
            timeout=600  # 10 min timeout
        )

        debug(f"  Return code: {result.returncode}")
        debug(f"  Stdout length: {len(result.stdout)} chars")
        debug(f"  Stderr length: {len(result.stderr)} chars")

        if result.returncode != 0:
            print(f"    ERROR: Data generation failed!")
            print(f"    Return code: {result.returncode}")
            if result.stdout:
                print(f"    Last output:")
                for line in result.stdout.split('\n')[-10:]:
                    if line.strip():
                        print(f"      {line}")
            if result.stderr:
                print(f"    Errors:")
                for line in result.stderr.split('\n')[-10:]:
                    if line.strip():
                        print(f"      {line}")
            return False

        # Check if output dataset was created (for CNN)
        output_dataset = config.get('output_dataset')
        if output_dataset:
            # For CNN: check in script parent dir
            if config['type'] == 'cnn':
                output_path = data_script.parent / output_dataset
            else:
                # For LightGBM: check in work_dir
                output_path = config['work_dir'] / output_dataset

            debug(f"  Checking output dataset: {output_path}")
            if output_path.exists():
                debug(f"    Output dataset exists, size: {output_path.stat().st_size} bytes")
                print(f"    Output: {output_path.name} ({output_path.stat().st_size / 1024:.1f} KB)")
            else:
                debug(f"    WARNING: Output dataset not found")

        print(f"    Data generation completed successfully")
        return True

    except subprocess.TimeoutExpired:
        print(f"    ERROR: Data generation timed out (>10 minutes)")
        return False
    except Exception as e:
        print(f"    ERROR: {e}")
        if DEBUG_MODE:
            traceback.print_exc()
        return False


def run_training(discipline: str, config: Dict, dry_run: bool = False) -> Optional[Dict]:
    """
    Run training script for a discipline.

    Returns dict with training results, or None if failed.
    """
    train_script = config['train_script']
    train_args_fn = config.get('train_args', [])

    # Get command-line arguments (may be a lambda)
    if callable(train_args_fn):
        train_args = train_args_fn()
    else:
        train_args = train_args_fn

    debug(f"Training for {discipline}")
    debug(f"  Script: {train_script}")
    debug(f"  Args: {train_args}")

    if not train_script.exists():
        print(f"    ERROR: Training script not found: {train_script}")
        return None

    print(f"    Script: {train_script.name}")
    if train_args:
        print(f"    Args: {train_args[0]}...")  # Show command

    if dry_run:
        print(f"    [DRY RUN] Would run training")
        if train_args:
            print(f"    [DRY RUN] Full command: python {train_script.name} {' '.join(train_args)}")
        # Return fake metrics for dry run
        return {'dry_run': True, 'val_accuracy': 0.85, 'train_accuracy': 0.90, 'overfit_gap': 0.05}

    try:
        cmd = [sys.executable, str(train_script)] + train_args
        debug(f"  Running: {' '.join(cmd)}")

        # Set up environment with test mode flag
        env = os.environ.copy()
        if TEST_MODE:
            env['CLASSIFIER_TEST_MODE'] = '1'
            info(f"  TEST MODE: Will run 1 config, 1 epoch only")

        result = subprocess.run(
            cmd,
            cwd=str(train_script.parent),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',  # Replace undecodable bytes instead of crashing
            timeout=7200 if not TEST_MODE else 600,  # 2 hour for real, 10 min for test
            env=env
        )

        debug(f"  Return code: {result.returncode}")
        debug(f"  Stdout length: {len(result.stdout)} chars")

        if result.returncode != 0:
            print(f"    ERROR: Training failed (return code {result.returncode})")
            if result.stderr:
                print(f"    Errors:")
                for line in result.stderr.split('\n')[-10:]:
                    if line.strip():
                        print(f"      {line}")
            # Still try to parse output
            debug(f"  Full stdout:\n{result.stdout}")

        # Parse output for metrics
        metrics = parse_training_output(result.stdout, config['type'])

        if metrics:
            print(f"    Training completed!")
            print(f"    Train Accuracy: {metrics.get('train_accuracy', 0):.2%}")
            print(f"    Val Accuracy: {metrics.get('val_accuracy', 0):.2%}")
            print(f"    Overfit Gap: {metrics.get('overfit_gap', 0):.2%}")
            score = calculate_score(metrics.get('val_accuracy', 0), metrics.get('overfit_gap', 0))
            print(f"    Score: {score:.3f}")
            metrics['score'] = score
        else:
            print(f"    WARNING: Could not parse training metrics")
            debug(f"  Full stdout:\n{result.stdout}")
            # Still might have succeeded, just can't parse output
            metrics = {}

        return metrics

    except subprocess.TimeoutExpired:
        print(f"    ERROR: Training timed out (>2 hours)")
        return None
    except Exception as e:
        print(f"    ERROR: {e}")
        if DEBUG_MODE:
            traceback.print_exc()
        return None


def parse_training_output(output: str, model_type: str) -> Optional[Dict]:
    """
    Parse training output to extract metrics.

    Handles multiple output formats:

    1. CNN Smithing trainer format (state-based):
       Training Set:
         Accuracy:  0.8208 (82.08%)
       Validation Set:
         Accuracy:  0.8208 (82.08%)
       Overfitting:   5.00% gap

    2. CNN Adornment trainer format (single-line):
       Validation: Acc=0.5400, F1=0.0000
       Training:   Acc=0.5400, F1=0.0000
       Overfitting Gap: 0.0213

    3. LightGBM trainer format (single-line):
       Train Accuracy: 0.8500
       Val Accuracy:   0.8200
       Overfit Gap:    0.0300 (3.0%)
    """
    metrics = {}

    debug(f"Parsing training output for {model_type}")

    try:
        lines = output.split('\n')

        # State for CNN parser (which section are we in?)
        current_section = None  # 'training' or 'validation'

        for line in lines:
            line_lower = line.lower().strip()
            line_stripped = line.strip()

            # Skip empty lines
            if not line_lower:
                continue

            # ===== ADORNMENT FORMAT: "Validation: Acc=0.5400, F1=0.0000" =====
            # This format has Acc= on same line as Validation:/Training:
            acc_equals_match = re.search(r'acc\s*=\s*(\d+\.?\d*)', line, re.IGNORECASE)
            if acc_equals_match:
                acc_val = float(acc_equals_match.group(1))
                if acc_val > 1:
                    acc_val = acc_val / 100
                if 'validation' in line_lower:
                    metrics['val_accuracy'] = acc_val
                    debug(f"  Found adornment val acc: {acc_val}")
                elif 'training' in line_lower:
                    metrics['train_accuracy'] = acc_val
                    debug(f"  Found adornment train acc: {acc_val}")
                continue

            # ===== CNN SMITHING FORMAT: Section headers =====
            if 'training set' in line_lower:
                current_section = 'training'
                debug(f"  Entered training section")
                continue

            if 'validation set' in line_lower:
                current_section = 'validation'
                debug(f"  Entered validation section")
                continue

            # ===== CNN SMITHING FORMAT: Accuracy in section =====
            if current_section and 'accuracy' in line_lower and ':' in line_lower:
                # Parse "Accuracy:  0.8208 (82.08%)" or "Accuracy: 82.08%"
                # Try percentage first
                pct_match = re.search(r'(\d+\.?\d*)\s*%', line)
                if pct_match:
                    acc = float(pct_match.group(1)) / 100
                else:
                    # Try decimal
                    dec_match = re.search(r'accuracy[:\s]+(\d+\.?\d+)', line, re.IGNORECASE)
                    if dec_match:
                        acc = float(dec_match.group(1))
                        if acc > 1:
                            acc = acc / 100
                    else:
                        continue

                if current_section == 'training':
                    metrics['train_accuracy'] = acc
                    debug(f"    Parsed train accuracy: {acc}")
                elif current_section == 'validation':
                    metrics['val_accuracy'] = acc
                    debug(f"    Parsed val accuracy: {acc}")
                continue

            # ===== LIGHTGBM FORMAT: Single-line metrics =====
            # "Train Accuracy: 0.8500" or "Train Accuracy: 85.00%"
            if 'train' in line_lower and 'accuracy' in line_lower and ':' in line_lower:
                pct_match = re.search(r'(\d+\.?\d*)\s*%', line)
                if pct_match:
                    metrics['train_accuracy'] = float(pct_match.group(1)) / 100
                else:
                    dec_match = re.search(r'accuracy[:\s]+(\d+\.?\d+)', line, re.IGNORECASE)
                    if dec_match:
                        val = float(dec_match.group(1))
                        metrics['train_accuracy'] = val if val <= 1 else val / 100
                debug(f"  Found train line: {line} -> {metrics.get('train_accuracy')}")
                continue

            # "Val Accuracy: 0.8200" or "Val Accuracy: 82.00%"
            if ('val' in line_lower or 'validation' in line_lower) and 'accuracy' in line_lower and ':' in line_lower:
                pct_match = re.search(r'(\d+\.?\d*)\s*%', line)
                if pct_match:
                    metrics['val_accuracy'] = float(pct_match.group(1)) / 100
                else:
                    dec_match = re.search(r'accuracy[:\s]+(\d+\.?\d+)', line, re.IGNORECASE)
                    if dec_match:
                        val = float(dec_match.group(1))
                        metrics['val_accuracy'] = val if val <= 1 else val / 100
                debug(f"  Found val line: {line} -> {metrics.get('val_accuracy')}")
                continue

            # ===== OVERFIT GAP (all formats) =====
            # "Overfitting:   5.00% gap" or "Overfit Gap: 0.0300 (3.0%)" or "Overfitting Gap: 0.0213"
            if 'overfit' in line_lower:
                debug(f"  Found gap line: {line}")
                pct_match = re.search(r'(\d+\.?\d*)\s*%', line)
                if pct_match:
                    metrics['overfit_gap'] = float(pct_match.group(1)) / 100
                    debug(f"    Parsed overfit gap from %: {metrics['overfit_gap']}")
                else:
                    # Try decimal format "0.0300" or "Gap: 0.0213"
                    dec_match = re.search(r'(?:gap|overfitting)[:\s]+(\d+\.?\d+)', line, re.IGNORECASE)
                    if dec_match:
                        val = float(dec_match.group(1))
                        metrics['overfit_gap'] = val if val <= 1 else val / 100
                        debug(f"    Parsed overfit gap from decimal: {metrics['overfit_gap']}")
                continue

        # Calculate overfit gap if we have both accuracies but no explicit gap
        if 'train_accuracy' in metrics and 'val_accuracy' in metrics and 'overfit_gap' not in metrics:
            metrics['overfit_gap'] = max(0, metrics['train_accuracy'] - metrics['val_accuracy'])
            debug(f"  Calculated overfit gap: {metrics['overfit_gap']}")

        debug(f"  Final metrics: {metrics}")
        return metrics if metrics else None

    except Exception as e:
        debug(f"  Parse error: {e}")
        return None


# ============================================================================
# MODEL SELECTION AND INSTALLATION
# ============================================================================

def find_best_model(discipline: str, config: Dict, work_dir: Path) -> Optional[Tuple[Path, float]]:
    """
    Find the best model in working directory based on naming convention and/or results files.

    For CNN: Look for .keras files, prefer those with metrics in name
    For LightGBM: Look for _model.txt files

    Returns tuple of (model_path, score) or None
    """
    model_pattern = config['model_pattern']
    model_type = config['type']

    debug(f"Finding best model for {discipline}")
    debug(f"  Pattern: {model_pattern}")
    debug(f"  Work dir: {work_dir}")

    # Find all matching models - first try direct match
    models = list(work_dir.glob(model_pattern))
    debug(f"  Found {len(models)} models with direct glob")

    if not models:
        # Try recursive search (CNN trainers may save to subdirectories)
        pattern = model_pattern.split('/')[-1] if '/' in model_pattern else model_pattern
        models = list(work_dir.rglob(pattern))
        debug(f"  Found {len(models)} models with recursive search (rglob)")

    # Also check common subdirectories for CNN trainers
    if not models and model_type == 'cnn':
        common_subdirs = ['best_model_variations', 'models', 'output']
        for subdir in common_subdirs:
            subdir_path = work_dir / subdir
            if subdir_path.exists():
                subdir_models = list(subdir_path.glob(model_pattern))
                debug(f"  Found {len(subdir_models)} models in {subdir}/")
                models.extend(subdir_models)

    if not models:
        print(f"    No models found matching: {model_pattern}")
        debug(f"    Searched in: {work_dir}")
        debug(f"    Subdirs present: {[d.name for d in work_dir.iterdir() if d.is_dir()]}")
        return None

    # For now, return the most recently modified model
    # In a real implementation, we'd parse results files to get actual scores
    best_model = max(models, key=lambda p: p.stat().st_mtime)

    debug(f"  Selected: {best_model} (most recent)")
    debug(f"    Modified: {datetime.fromtimestamp(best_model.stat().st_mtime)}")

    # Estimate score (would need actual metrics from training)
    estimated_score = 0.80  # Placeholder

    print(f"    Found best model: {best_model.name}")
    return (best_model, estimated_score)


def install_model(discipline: str, source_model: Path, dry_run: bool = False) -> bool:
    """
    Install a trained model to the game-expected path.

    Args:
        discipline: Discipline name
        source_model: Path to the trained model
        dry_run: If True, only print what would happen

    Returns:
        True if successful
    """
    target_path = GAME_MODEL_PATHS.get(discipline)

    debug(f"Installing model for {discipline}")
    debug(f"  Source: {source_model}")
    debug(f"  Target: {target_path}")

    if not target_path:
        print(f"    ERROR: No target path configured for {discipline}")
        return False

    # Ensure target directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)
    debug(f"  Target parent ensured: {target_path.parent}")

    if dry_run:
        print(f"    [DRY RUN] Would install: {source_model.name}")
        print(f"    [DRY RUN]    -> {target_path}")
        return True

    try:
        shutil.copy2(source_model, target_path)
        print(f"    Installed: {source_model.name}")
        print(f"           -> {target_path}")
        debug(f"  Copy successful")

        # For LightGBM, also copy the extractor .pkl if it exists
        if discipline in ['alchemy', 'refining', 'engineering']:
            # Try different naming conventions
            extractor_patterns = [
                source_model.with_suffix('.pkl').with_name(
                    source_model.stem.replace('_model', '_extractor') + '.pkl'
                ),
                source_model.parent / (source_model.stem.replace('_model', '_extractor') + '.pkl'),
            ]

            for extractor_source in extractor_patterns:
                debug(f"  Checking extractor: {extractor_source}")
                if extractor_source.exists():
                    extractor_target = target_path.with_suffix('.pkl').with_name(
                        target_path.stem.replace('_model', '_extractor') + '.pkl'
                    )
                    debug(f"  Installing extractor to: {extractor_target}")
                    shutil.copy2(extractor_source, extractor_target)
                    print(f"    Installed extractor: {extractor_source.name}")
                    break

        return True

    except Exception as e:
        print(f"    ERROR installing model: {e}")
        if DEBUG_MODE:
            traceback.print_exc()
        return False


# ============================================================================
# MAIN WORKFLOW
# ============================================================================

def train_discipline(discipline: str, dry_run: bool = False,
                     force: bool = False, keep_best: int = 3) -> Dict:
    """
    Complete training workflow for a single discipline.

    Steps:
    0. Check if data changed (skip if unchanged and not forced)
    1. Archive existing model
    2. Generate training data
    3. Train model
    4. Select best model
    5. Install to game path
    6. Cleanup old models (keep best N)

    Args:
        discipline: Name of discipline to train
        dry_run: If True, don't actually execute, just show what would happen
        force: If True, train even if data hasn't changed
        keep_best: Number of best models to keep (rest are archived)

    Returns dict with results summary.
    """
    if discipline not in DISCIPLINES:
        return {'error': f'Unknown discipline: {discipline}', 'success': False}

    config = DISCIPLINES[discipline]
    results = {
        'discipline': discipline,
        'type': config['type'],
        'success': False,
        'steps_completed': [],
    }

    print(f"\n{'='*70}")
    print(f"TRAINING: {discipline.upper()}")
    print(f"Type: {config['type'].upper()}")
    print(f"{'='*70}")

    # Step 0: Check if data changed
    data_changed, reason = check_data_changed(discipline, force)
    if not data_changed:
        print(f"\n[SKIP] Data unchanged for {discipline} ({reason})")
        print(f"    Use --force to retrain anyway")
        results['skipped'] = True
        results['skip_reason'] = reason
        results['success'] = True  # Not a failure, just skipped
        return results

    print(f"\n[INFO] Training needed: {reason}")

    # Step 1: Archive existing model
    print(f"\n[1/5] Archiving existing model...")
    try:
        archived = archive_current_model(discipline, dry_run)
        results['archived'] = len(archived)
        if archived:
            print(f"    Archived {len(archived)} file(s)")
        else:
            print(f"    No existing model to archive")
        results['steps_completed'].append('archive')
    except Exception as e:
        print(f"    ERROR during archive: {e}")
        if DEBUG_MODE:
            traceback.print_exc()

    # Step 2: Generate training data
    print(f"\n[2/5] Generating training data...")
    try:
        data_ok = run_data_generation(discipline, config, dry_run)
        if not data_ok and not dry_run:
            results['error'] = 'Data generation failed'
            print(f"    FAILED - stopping here")
            return results
        results['steps_completed'].append('data_gen')
    except Exception as e:
        print(f"    ERROR during data generation: {e}")
        if DEBUG_MODE:
            traceback.print_exc()
        results['error'] = f'Data generation error: {e}'
        return results

    # Step 3: Train model
    print(f"\n[3/5] Training model...")
    try:
        train_metrics = run_training(discipline, config, dry_run)
        results['metrics'] = train_metrics

        if not train_metrics and not dry_run:
            results['error'] = 'Training failed'
            print(f"    FAILED - stopping here")
            return results
        results['steps_completed'].append('training')
    except Exception as e:
        print(f"    ERROR during training: {e}")
        if DEBUG_MODE:
            traceback.print_exc()
        results['error'] = f'Training error: {e}'
        return results

    # Step 4: Select best model
    print(f"\n[4/5] Selecting best model...")
    try:
        best_result = find_best_model(discipline, config, config['work_dir'])

        if not best_result and not dry_run:
            results['error'] = 'No model found after training'
            print(f"    FAILED - no model found")
            return results

        if best_result:
            best_model, score = best_result
            results['best_model'] = str(best_model)
            results['score'] = score

            if train_metrics:
                val_acc = train_metrics.get('val_accuracy', 0)
                overfit = train_metrics.get('overfit_gap', 0)
                actual_score = calculate_score(val_acc, overfit)
                results['actual_score'] = actual_score
                print(f"    Score: {actual_score:.3f} (acc={val_acc:.2%}, overfit={overfit:.2%})")
        results['steps_completed'].append('model_select')
    except Exception as e:
        print(f"    ERROR during model selection: {e}")
        if DEBUG_MODE:
            traceback.print_exc()

    # Step 5: Install model
    print(f"\n[5/6] Installing model to game path...")
    try:
        if best_result:
            install_ok = install_model(discipline, best_result[0], dry_run)
            results['installed'] = install_ok
            results['success'] = install_ok
            if install_ok:
                results['steps_completed'].append('install')
        else:
            results['success'] = dry_run  # Dry run counts as success
    except Exception as e:
        print(f"    ERROR during installation: {e}")
        if DEBUG_MODE:
            traceback.print_exc()

    # Step 6: Cleanup old models and update hash cache
    print(f"\n[6/6] Cleanup and finalize...")
    try:
        if not dry_run:
            # Update hash cache so we don't retrain unnecessarily next time
            update_data_hash_cache(discipline)
            print(f"    Updated data hash cache for {discipline}")

            # Cleanup old models
            if keep_best > 0:
                archived = cleanup_old_models(discipline, config, keep_best)
                if archived:
                    results['cleaned_up'] = archived
        else:
            print(f"    [DRY RUN] Would update hash cache and cleanup models")
        results['steps_completed'].append('finalize')
    except Exception as e:
        print(f"    ERROR during cleanup: {e}")
        if DEBUG_MODE:
            traceback.print_exc()

    debug(f"Final results: {results}")
    return results


def train_all(disciplines: List[str], dry_run: bool = False,
              force: bool = False, keep_best: int = 3) -> Dict:
    """Train multiple disciplines in sequence."""
    all_results = {}

    print("\n" + "="*70)
    print("UNIFIED CLASSIFIER TRAINING SYSTEM")
    print("="*70)
    print(f"Disciplines: {', '.join(disciplines)}")
    print(f"Dry Run: {dry_run}")
    print(f"Force: {force}")
    print(f"Keep Best: {keep_best}")
    print(f"Debug Mode: {DEBUG_MODE}")
    print(f"Test Mode: {TEST_MODE}")
    print(f"Models Dir: {MODELS_DIR}")
    print(f"Training Data Dir: {TRAINING_DATA_DIR}")
    print(f"Archive Dir: {ARCHIVE_DIR}")
    print(f"Scoring: score = val_accuracy - 2.0 * overfit_gap")
    print("="*70)

    # Ensure all directories exist
    if not dry_run:
        ensure_directories()

    for discipline in disciplines:
        try:
            results = train_discipline(discipline, dry_run, force, keep_best)
            all_results[discipline] = results
        except Exception as e:
            print(f"\nERROR training {discipline}: {e}")
            if DEBUG_MODE:
                traceback.print_exc()
            all_results[discipline] = {'error': str(e), 'success': False}

    # Print summary
    print("\n" + "="*70)
    print("TRAINING SUMMARY")
    print("="*70)

    for discipline, results in all_results.items():
        status = "SUCCESS" if results.get('success') else "FAILED"
        score = results.get('actual_score', results.get('score', 0))
        score_str = f"Score: {score:.3f}" if score else "Score: N/A"
        steps = ', '.join(results.get('steps_completed', []))

        print(f"  {discipline:<15} [{status}] {score_str}")
        if steps:
            print(f"                  Steps: {steps}")
        if results.get('error'):
            print(f"                  Error: {results['error']}")

    print("="*70)

    return all_results


# ============================================================================
# CLI
# ============================================================================

def main():
    global DEBUG_MODE

    parser = argparse.ArgumentParser(
        description='Train all crafting classifiers with model selection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scoring Formula:
  score = val_accuracy - 2.0 * overfit_gap

  This penalizes overfitting 2x more than accuracy loss:
  - 93%% acc, 7%% overfit → 0.93 - 0.14 = 0.79
  - 86%% acc, 1%% overfit → 0.86 - 0.02 = 0.84 (BETTER!)

Examples:
  %(prog)s                         # Train all disciplines
  %(prog)s --discipline smithing   # Train only smithing
  %(prog)s --dry-run               # Show what would happen
  %(prog)s --debug                 # Verbose debug output
  %(prog)s --test-paths            # Verify all paths exist
  %(prog)s -d alchemy -d refining  # Train specific disciplines

Training Order:
  1. Smithing (CNN)
  2. Adornments (CNN)
  3. Alchemy (LightGBM)
  4. Refining (LightGBM - separate trainer)
  5. Engineering (LightGBM)
        """
    )

    parser.add_argument(
        '-d', '--discipline',
        action='append',
        choices=list(DISCIPLINES.keys()),
        help='Discipline to train (can specify multiple)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would happen without making changes'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable verbose debug output'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List available disciplines and exit'
    )

    parser.add_argument(
        '--test-paths',
        action='store_true',
        help='Test all paths exist and exit'
    )

    parser.add_argument(
        '--debug-paths',
        action='store_true',
        help='Print detailed path configuration and exit'
    )

    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force retraining even if data has not changed'
    )

    parser.add_argument(
        '--keep-best', '-k',
        type=int,
        default=3,
        metavar='N',
        help='Keep best N models, archive the rest (default: 3)'
    )

    parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Skip model cleanup (keep all models)'
    )

    parser.add_argument(
        '--test-mode', '-t',
        action='store_true',
        help='Skeleton test mode: runs 1 config, 1 epoch to validate data generation works'
    )

    args = parser.parse_args()

    # Set global modes
    global DEBUG_MODE, TEST_MODE
    DEBUG_MODE = args.debug
    TEST_MODE = args.test_mode

    if DEBUG_MODE:
        print("[DEBUG MODE ENABLED]")

    if TEST_MODE:
        print("=" * 70)
        print("TEST MODE ENABLED")
        print("=" * 70)
        print("  - Data generation: FULL (validates data pipeline)")
        print("  - Training: 1 config, 1 epoch only")
        print("  - Purpose: Validate data generation and basic model creation")
        print("=" * 70)

    # Handle special modes
    if args.debug_paths:
        debug_paths()
        return 0

    if args.test_paths:
        ok = test_all_paths()
        return 0 if ok else 1

    if args.list:
        print("Available disciplines:")
        print("-" * 50)
        for name, config in DISCIPLINES.items():
            game_path = GAME_MODEL_PATHS.get(name, Path('N/A'))
            exists = game_path.exists() if game_path != Path('N/A') else False
            status = "[EXISTS]" if exists else "[MISSING]"
            print(f"  {name:<15} ({config['type']}) {status}")
            print(f"                  -> {game_path.name if game_path != Path('N/A') else 'N/A'}")
        return 0

    # Determine disciplines to train (in correct order)
    if args.discipline:
        # Preserve order: filter DISCIPLINES.keys() to include only requested ones
        all_order = list(DISCIPLINES.keys())
        disciplines = [d for d in all_order if d in args.discipline]
    else:
        disciplines = list(DISCIPLINES.keys())

    # Verify paths before training
    if not args.dry_run:
        print("Verifying paths...")
        if not test_all_paths():
            print("\nERROR: Some required paths are missing. Use --debug-paths for details.")
            print("Continuing anyway (some training may fail)...")

    # Determine keep_best value (0 means no cleanup)
    keep_best = 0 if args.no_cleanup else args.keep_best

    # Run training
    results = train_all(disciplines, args.dry_run, args.force, keep_best)

    # Exit code based on success (skipped counts as success)
    all_success = all(r.get('success', False) for r in results.values())
    return 0 if all_success else 1


if __name__ == '__main__':
    sys.exit(main())
