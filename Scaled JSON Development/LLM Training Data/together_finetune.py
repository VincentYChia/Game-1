"""
Together.ai Fine-Tuning Script

Simple script to launch fine-tuning jobs on Together.ai.

Usage:
    python together_finetune.py

Prerequisites:
    pip install together
    export TOGETHER_API_KEY="your-key"
"""

import os
from pathlib import Path
from together import Together

# =============================================================================
# CONFIGURATION - Edit these values
# =============================================================================

# LLM model for text-only disciplines (alchemy, refining, engineering)
LLM_MODEL = "meta-llama/Llama-3.2-3B-Instruct"

# VLM model for vision disciplines (smithing, adornment)
VLM_MODEL = "meta-llama/Llama-Vision-Free"  # or another VLM model

# Training parameters
N_EPOCHS = 3
LEARNING_RATE = 1e-5
BATCH_SIZE = 4
LORA = True

# =============================================================================
# MAIN
# =============================================================================

def main():
    # Check API key
    if not os.environ.get("TOGETHER_API_KEY"):
        print("Error: Set TOGETHER_API_KEY environment variable")
        print("  export TOGETHER_API_KEY='your-key'")
        return

    client = Together()

    # Find JSONL files
    output_dir = Path(__file__).parent / "jsonl_outputs"
    if not output_dir.exists():
        print(f"Error: {output_dir} not found. Run convert_to_jsonl.py first.")
        return

    jsonl_files = sorted(output_dir.glob("*.jsonl"))
    if not jsonl_files:
        print("No JSONL files found.")
        return

    # Show files
    print("Available JSONL files:")
    print("-" * 50)
    for i, f in enumerate(jsonl_files, 1):
        count = sum(1 for _ in open(f))
        print(f"  {i}. {f.name} ({count} entries)")

    # Select file
    print()
    sel = input(f"Select file (1-{len(jsonl_files)}): ").strip()
    try:
        idx = int(sel) - 1
        if not (0 <= idx < len(jsonl_files)):
            raise ValueError()
    except ValueError:
        print("Invalid selection.")
        return

    selected_file = jsonl_files[idx]
    discipline = selected_file.stem.split("_")[0]

    # Determine model based on discipline
    vlm_disciplines = {"smithing", "adornment"}
    is_vlm = discipline in vlm_disciplines
    model = VLM_MODEL if is_vlm else LLM_MODEL

    print(f"\nFile: {selected_file.name}")
    print(f"Model: {model} ({'VLM' if is_vlm else 'LLM'})")
    print(f"Epochs: {N_EPOCHS}, LR: {LEARNING_RATE}, Batch: {BATCH_SIZE}, LoRA: {LORA}")

    confirm = input("\nStart fine-tuning? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    # Upload and start job
    print("\nUploading file...")
    file_resp = client.files.upload(str(selected_file), check=True)
    print(f"Uploaded: {file_resp.id}")

    print("Starting fine-tuning...")
    job = client.fine_tuning.create(
        training_file=file_resp.id,
        model=model,
        n_epochs=N_EPOCHS,
        learning_rate=LEARNING_RATE,
        batch_size=BATCH_SIZE,
        lora=LORA,
        suffix=f"crafting-{discipline}",
    )

    print(f"\nJob started: {job.id}")
    print(f"Check status: together fine-tuning retrieve {job.id}")


if __name__ == "__main__":
    main()
