#!/usr/bin/env python3
"""Simple Together.ai Fine-tuning Script"""

import os
from together import Together

# ============================================================================
# CHANGE THESE EVERY RUN
# ============================================================================

FILE_ID = "file-fd51d4bb-2f50-43ca-bbf4-8698fda360f3"  # Your uploaded file ID
JOB_NAME = "Combined_Crafting_1"                          # Name/suffix for your job
MODEL = "google/gemma-3-4b-it-VLM"                    # Model to fine-tune

# Parameters
N_EPOCHS = 5
BATCH_SIZE = 8
LEARNING_RATE = 2e-3
USE_LORA = True
TRAIN_VISION = True
TRAIN_ON_INPUTS = "auto"  # "auto", "true", or "false"

# ============================================================================
# API KEYS (from environment)
# ============================================================================

TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY")
WANDB_API_KEY = os.environ.get("WANDB_API_KEY")  # Optional

if not TOGETHER_API_KEY:
    raise ValueError("TOGETHER_API_KEY environment variable not set")

# ============================================================================
# RUN THE JOB
# ============================================================================

client = Together(api_key=TOGETHER_API_KEY)

response = client.fine_tuning.create(
    training_file=FILE_ID,
    model=MODEL,
    suffix=JOB_NAME,
    lora=USE_LORA,
    train_vision=TRAIN_VISION,
    train_on_inputs=TRAIN_ON_INPUTS,
    n_epochs=N_EPOCHS,
    batch_size=BATCH_SIZE,
    learning_rate=LEARNING_RATE,
    wandb_api_key=WANDB_API_KEY if WANDB_API_KEY else None,
)

print(f"✓ Job created: {response.id}")
print(f"  Dashboard: https://api.together.xyz/jobs/{response.id}")
if WANDB_API_KEY:
    print(f"  WandB tracking enabled")