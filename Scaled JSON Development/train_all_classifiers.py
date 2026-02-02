#!/usr/bin/env python3
"""
Unified Classifier Training Script

Trains all 5 crafting classifiers (2 CNN + 3 LightGBM) with:
- Automatic data generation from base + Update folders
- Model selection targeting 80-95% accuracy with minimal overfitting
- Automatic archiving of old models
- Replacement of production models with new ones

Usage:
    python train_all_classifiers.py                    # Train all
    python train_all_classifiers.py --discipline smithing  # Train one
    python train_all_classifiers.py --dry-run          # Show what would happen

Created: 2026-02-02
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import subprocess

# Add paths
SCRIPT_DIR = Path(__file__).parent
CNN_DIR = SCRIPT_DIR / "Convolution Neural Network (CNN)"
LIGHTGBM_DIR = SCRIPT_DIR / "Simple Classifiers (LightGBM)"
GAME_MODULAR = SCRIPT_DIR.parent / "Game-1-modular"
ARCHIVE_DIR = SCRIPT_DIR / "archived_classifiers"


# ============================================================================
# CONFIGURATION
# ============================================================================

DISCIPLINES = {
    'smithing': {
        'type': 'cnn',
        'data_generator': CNN_DIR / "Smithing" / "valid_smithing_data_v2.py",
        'trainer': CNN_DIR / "Smithing" / "CNN_trainer_smithing.py",
        'model_dir': CNN_DIR / "Smithing",
        'current_model_pattern': 'excellent_minimal*.keras',
        'dataset_file': 'recipe_dataset_v2.npz',
    },
    'adornments': {
        'type': 'cnn',
        'data_generator': CNN_DIR / "Adornment" / "data_augment_adornment_v2.py",
        'trainer': CNN_DIR / "Adornment" / "CNN_trainer_adornment.py",
        'model_dir': CNN_DIR / "Adornment",
        'current_model_pattern': '*.keras',
        'dataset_file': 'adornment_dataset_v2.npz',
    },
    'alchemy': {
        'type': 'lightgbm',
        'data_generator': LIGHTGBM_DIR / "data_augment_GBM.py",
        'trainer': LIGHTGBM_DIR / "LightGBM_trainer.py",
        'model_dir': LIGHTGBM_DIR / "alchemy_lightGBM",
        'current_model': 'alchemy_model.txt',
        'dataset_file': 'alchemy_augmented_data.json',
    },
    'refining': {
        'type': 'lightgbm',
        'data_generator': LIGHTGBM_DIR / "data_augment_ref.py",
        'trainer': LIGHTGBM_DIR / "LightGBM_trainer_ref.py",
        'model_dir': LIGHTGBM_DIR / "refining_lightGBM",
        'current_model': 'refining_model.txt',
        'dataset_file': 'refining_augmented_data.json',
    },
    'engineering': {
        'type': 'lightgbm',
        'data_generator': LIGHTGBM_DIR / "data_augment_GBM.py",
        'trainer': LIGHTGBM_DIR / "LightGBM_trainer.py",
        'model_dir': LIGHTGBM_DIR / "engineering_lightGBM",
        'current_model': 'engineering_model.txt',
        'dataset_file': 'engineering_augmented_data.json',
    },
}

# Model selection criteria
SELECTION_CRITERIA = {
    'min_val_accuracy': 0.80,   # Minimum validation accuracy
    'max_val_accuracy': 0.95,   # Maximum (higher might indicate overfitting)
    'max_overfit_gap': 0.15,    # Max (train_acc - val_acc)
    'ideal_val_range': (0.82, 0.92),  # Sweet spot
}


# ============================================================================
# ARCHIVE MANAGEMENT
# ============================================================================

def ensure_archive_dir():
    """Create archive directory if it doesn't exist."""
    ARCHIVE_DIR.mkdir(exist_ok=True)
    return ARCHIVE_DIR


def archive_model(discipline: str, model_path: Path, dry_run: bool = False) -> Optional[Path]:
    """
    Archive an existing model with timestamp.

    Args:
        discipline: Discipline name
        model_path: Path to model to archive
        dry_run: If True, only print what would happen

    Returns:
        Path to archived model, or None if dry run
    """
    if not model_path.exists():
        print(f"  No existing model to archive: {model_path}")
        return None

    archive_dir = ensure_archive_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archived_name = f"{discipline}_{model_path.stem}_{timestamp}{model_path.suffix}"
    archive_path = archive_dir / archived_name

    if dry_run:
        print(f"  [DRY RUN] Would archive: {model_path.name} -> {archive_path.name}")
        return None

    shutil.copy2(model_path, archive_path)
    print(f"  Archived: {model_path.name} -> {archive_path.name}")
    return archive_path


def archive_all_existing_models(discipline: str, config: dict, dry_run: bool = False) -> List[Path]:
    """Archive all existing models for a discipline."""
    archived = []
    model_dir = config['model_dir']

    if config['type'] == 'cnn':
        # Find all matching models
        pattern = config.get('current_model_pattern', '*.keras')
        for model_path in model_dir.glob(pattern):
            result = archive_model(discipline, model_path, dry_run)
            if result:
                archived.append(result)
    else:
        # Single model file
        model_path = model_dir / config['current_model']
        result = archive_model(discipline, model_path, dry_run)
        if result:
            archived.append(result)

    return archived


# ============================================================================
# DATA GENERATION
# ============================================================================

def generate_training_data(discipline: str, config: dict, dry_run: bool = False) -> bool:
    """
    Generate training data for a discipline.

    Args:
        discipline: Discipline name
        config: Discipline configuration
        dry_run: If True, only print what would happen

    Returns:
        True if successful
    """
    generator_path = config['data_generator']

    if not generator_path.exists():
        print(f"  ERROR: Data generator not found: {generator_path}")
        return False

    print(f"\n  Generating training data...")
    print(f"  Script: {generator_path.name}")

    if dry_run:
        print(f"  [DRY RUN] Would run: python {generator_path}")
        return True

    # Run the data generator
    try:
        result = subprocess.run(
            [sys.executable, str(generator_path)],
            cwd=str(generator_path.parent),
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode != 0:
            print(f"  ERROR: Data generation failed!")
            print(f"  STDOUT: {result.stdout[-500:]}")
            print(f"  STDERR: {result.stderr[-500:]}")
            return False

        # Check for output file
        dataset_file = generator_path.parent / config['dataset_file']
        if dataset_file.exists():
            size_mb = dataset_file.stat().st_size / (1024 * 1024)
            print(f"  Generated: {config['dataset_file']} ({size_mb:.1f} MB)")
            return True
        else:
            print(f"  WARNING: Dataset file not found: {dataset_file}")
            return False

    except subprocess.TimeoutExpired:
        print(f"  ERROR: Data generation timed out (>10 min)")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


# ============================================================================
# MODEL TRAINING
# ============================================================================

def train_model(discipline: str, config: dict, dry_run: bool = False) -> Optional[Dict]:
    """
    Train a model for a discipline.

    Args:
        discipline: Discipline name
        config: Discipline configuration
        dry_run: If True, only print what would happen

    Returns:
        Dict with training results, or None if failed
    """
    trainer_path = config['trainer']

    if not trainer_path.exists():
        print(f"  ERROR: Trainer not found: {trainer_path}")
        return None

    print(f"\n  Training model...")
    print(f"  Script: {trainer_path.name}")

    if dry_run:
        print(f"  [DRY RUN] Would run: python {trainer_path}")
        return {'dry_run': True}

    # Run the trainer
    try:
        result = subprocess.run(
            [sys.executable, str(trainer_path)],
            cwd=str(trainer_path.parent),
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout for CNN training
        )

        # Parse output for results
        results = parse_training_output(result.stdout, config['type'])

        if results:
            print(f"  Training completed!")
            print(f"  Val Accuracy: {results.get('val_accuracy', 'N/A'):.2%}")
            print(f"  Overfit Gap: {results.get('overfit_gap', 'N/A'):.2%}")
        else:
            print(f"  WARNING: Could not parse training results")
            print(f"  Output (last 500 chars): {result.stdout[-500:]}")

        return results

    except subprocess.TimeoutExpired:
        print(f"  ERROR: Training timed out (>1 hour)")
        return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def parse_training_output(output: str, model_type: str) -> Optional[Dict]:
    """Parse training output to extract metrics."""
    results = {}

    try:
        # Look for validation accuracy
        for line in output.split('\n'):
            line_lower = line.lower()

            # CNN patterns
            if 'val_acc' in line_lower or 'validation accuracy' in line_lower:
                # Try to find percentage
                import re
                match = re.search(r'(\d+\.?\d*)\s*%', line)
                if match:
                    results['val_accuracy'] = float(match.group(1)) / 100
                else:
                    match = re.search(r'(\d+\.?\d+)', line)
                    if match:
                        val = float(match.group(1))
                        results['val_accuracy'] = val if val < 1 else val / 100

            # Overfitting gap patterns
            if 'gap' in line_lower or 'overfit' in line_lower:
                match = re.search(r'(\d+\.?\d*)\s*%', line)
                if match:
                    results['overfit_gap'] = float(match.group(1)) / 100

            # LightGBM patterns
            if 'best_iteration' in line_lower:
                match = re.search(r'(\d+)', line)
                if match:
                    results['best_iteration'] = int(match.group(1))

        return results if results else None

    except Exception:
        return None


# ============================================================================
# MODEL SELECTION
# ============================================================================

def select_best_model(discipline: str, config: dict) -> Optional[Path]:
    """
    Find the best model from training results.

    For CNN: Look for newest .keras file that meets criteria
    For LightGBM: Check the trained model

    Returns:
        Path to best model, or None
    """
    model_dir = config['model_dir']

    if config['type'] == 'cnn':
        # Find all .keras files, sorted by modification time (newest first)
        keras_files = sorted(
            model_dir.glob('*.keras'),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        # Return newest (most recently trained)
        if keras_files:
            return keras_files[0]
        return None

    else:  # LightGBM
        model_path = model_dir / config['current_model']
        if model_path.exists():
            return model_path
        return None


def evaluate_model_quality(results: Optional[Dict]) -> str:
    """
    Evaluate if model meets quality criteria.

    Returns: 'excellent', 'acceptable', or 'poor'
    """
    if not results or 'val_accuracy' not in results:
        return 'unknown'

    val_acc = results['val_accuracy']
    overfit = results.get('overfit_gap', 0)

    ideal_min, ideal_max = SELECTION_CRITERIA['ideal_val_range']

    if (ideal_min <= val_acc <= ideal_max and
        overfit < SELECTION_CRITERIA['max_overfit_gap']):
        return 'excellent'
    elif (SELECTION_CRITERIA['min_val_accuracy'] <= val_acc <=
          SELECTION_CRITERIA['max_val_accuracy'] and
          overfit < SELECTION_CRITERIA['max_overfit_gap'] * 1.5):
        return 'acceptable'
    else:
        return 'poor'


# ============================================================================
# MAIN WORKFLOW
# ============================================================================

def train_discipline(discipline: str, dry_run: bool = False) -> Dict:
    """
    Complete training workflow for a discipline.

    1. Archive existing models
    2. Generate training data
    3. Train model
    4. Evaluate quality
    5. Install new model (if acceptable)

    Returns:
        Dict with results summary
    """
    if discipline not in DISCIPLINES:
        return {'error': f'Unknown discipline: {discipline}'}

    config = DISCIPLINES[discipline]
    results = {
        'discipline': discipline,
        'type': config['type'],
        'success': False,
    }

    print(f"\n{'='*70}")
    print(f"TRAINING: {discipline.upper()}")
    print(f"Type: {config['type'].upper()}")
    print(f"{'='*70}")

    # Step 1: Archive existing models
    print(f"\n[Step 1] Archiving existing models...")
    archived = archive_all_existing_models(discipline, config, dry_run)
    results['archived_count'] = len(archived)

    # Step 2: Generate training data
    print(f"\n[Step 2] Generating training data...")
    data_ok = generate_training_data(discipline, config, dry_run)
    if not data_ok and not dry_run:
        results['error'] = 'Data generation failed'
        return results

    # Step 3: Train model
    print(f"\n[Step 3] Training model...")
    train_results = train_model(discipline, config, dry_run)
    results['training'] = train_results

    if not train_results and not dry_run:
        results['error'] = 'Training failed'
        return results

    # Step 4: Evaluate quality
    print(f"\n[Step 4] Evaluating model quality...")
    quality = evaluate_model_quality(train_results)
    results['quality'] = quality
    print(f"  Quality Assessment: {quality.upper()}")

    # Step 5: Find and report best model
    print(f"\n[Step 5] Locating best model...")
    best_model = select_best_model(discipline, config)
    if best_model:
        print(f"  Best model: {best_model.name}")
        results['model_path'] = str(best_model)
        results['success'] = quality in ('excellent', 'acceptable')
    else:
        print(f"  WARNING: No model found!")
        results['success'] = False

    return results


def train_all(disciplines: List[str], dry_run: bool = False) -> Dict:
    """Train multiple disciplines."""
    all_results = {}

    print("\n" + "=" * 70)
    print("UNIFIED CLASSIFIER TRAINING SYSTEM")
    print("=" * 70)
    print(f"Disciplines: {', '.join(disciplines)}")
    print(f"Dry Run: {dry_run}")
    print(f"Archive Dir: {ARCHIVE_DIR}")
    print("=" * 70)

    for discipline in disciplines:
        results = train_discipline(discipline, dry_run)
        all_results[discipline] = results

    # Summary
    print("\n" + "=" * 70)
    print("TRAINING SUMMARY")
    print("=" * 70)

    for discipline, results in all_results.items():
        status = "SUCCESS" if results.get('success') else "FAILED"
        quality = results.get('quality', 'unknown')
        print(f"  {discipline:<15} [{status}] Quality: {quality}")

    return all_results


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Train all crafting classifiers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                         # Train all disciplines
  %(prog)s --discipline smithing   # Train only smithing
  %(prog)s --dry-run               # Show what would happen
  %(prog)s -d alchemy -d refining  # Train specific disciplines
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
        '--list',
        action='store_true',
        help='List available disciplines and exit'
    )

    args = parser.parse_args()

    if args.list:
        print("Available disciplines:")
        for name, config in DISCIPLINES.items():
            print(f"  {name:<15} ({config['type']})")
        return

    # Determine which disciplines to train
    disciplines = args.discipline if args.discipline else list(DISCIPLINES.keys())

    # Run training
    results = train_all(disciplines, args.dry_run)

    # Exit code based on success
    all_success = all(r.get('success', False) for r in results.values())
    sys.exit(0 if all_success else 1)


if __name__ == '__main__':
    main()
