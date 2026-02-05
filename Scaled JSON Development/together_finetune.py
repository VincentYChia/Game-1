"""
Together.ai Fine-Tuning Script for Crafting Models

Simple script to launch fine-tuning jobs on Together.ai.

Usage:
    python together_finetune.py

Prerequisites:
    pip install together
"""

import os
import json
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

# Default model for fine-tuning
MODEL = "google/gemma-3-4b-it"

# Training file path (relative to this script)
TRAINING_FILE = "./training_data/crafting_training_data.jsonl"

# Training parameters
N_EPOCHS = 3
LEARNING_RATE = 1e-5
BATCH_SIZE = 4
LORA = True
SUFFIX = "crafting-v1"


# =============================================================================
# MAIN
# =============================================================================

def get_api_key() -> str:
    """Get API key from environment or prompt user."""
    api_key = os.environ.get("TOGETHER_API_KEY")

    if not api_key:
        print("TOGETHER_API_KEY not found in environment.")
        api_key = input("Enter your Together.ai API key: ").strip()

        if not api_key:
            print("Error: API key is required.")
            exit(1)

        os.environ["TOGETHER_API_KEY"] = api_key

    return api_key


def main():
    print("=" * 60)
    print("Together.ai Fine-Tuning")
    print("=" * 60)

    # Check training file exists
    script_dir = Path(__file__).parent
    training_path = script_dir / TRAINING_FILE

    if not training_path.exists():
        print(f"\nError: Training file not found: {training_path}")
        print("Generate training data first with crafting_training_data.py")
        return

    print(f"\nTraining file: {training_path}")
    print(f"Model: {MODEL}")
    print(f"Epochs: {N_EPOCHS}")
    print(f"Learning rate: {LEARNING_RATE}")
    print(f"LoRA: {LORA}")

    # Get API key
    get_api_key()

    # Import together (after API key is set)
    try:
        from together import Together
    except ImportError:
        print("\nError: together package not installed.")
        print("Run: pip install together")
        return

    client = Together()

    # Confirm before proceeding
    print()
    confirm = input("Start fine-tuning job? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    # Upload file
    print("\nUploading training file...")
    file_resp = client.files.upload(str(training_path), check=True)
    file_id = file_resp.id
    print(f"File uploaded: {file_id}")

    # Create fine-tuning job
    print("\nStarting fine-tuning job...")
    job_resp = client.fine_tuning.create(
        training_file=file_id,
        model=MODEL,
        n_epochs=N_EPOCHS,
        learning_rate=LEARNING_RATE,
        batch_size=BATCH_SIZE,
        lora=LORA,
        suffix=SUFFIX,
    )

    job_id = job_resp.id
    print(f"\nJob started successfully!")
    print(f"Job ID: {job_id}")
    print(f"\nMonitor at: https://api.together.xyz/playground")


if __name__ == "__main__":
    main()
