#!/usr/bin/env python3
"""Simple Together.ai Fine-tuning Script"""

import os
from together import Together

# ============================================================================
# CHANGE THESE EVERY RUN
# ============================================================================

FILE_ID = "file-fb7be24e-7178-48bf-8757-b6a60b4838be"  # Your uploaded file ID
JOB_NAME = "test_adornment"                          # Name/suffix for your job
MODEL = "google/gemma-3-4b-it-VLM"                    # Model to fine-tune

# Parameters
N_EPOCHS = 5
BATCH_SIZE = 8
LEARNING_RATE = 1e-4
USE_LORA = True
TRAIN_VISION = True

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
    n_epochs=N_EPOCHS,
    batch_size=BATCH_SIZE,
    learning_rate=LEARNING_RATE,
    wandb_api_key=WANDB_API_KEY if WANDB_API_KEY else None,
)

print(f"✓ Job created: {response.id}")
print(f"  Dashboard: https://api.together.xyz/jobs/{response.id}")
if WANDB_API_KEY:
    print(f"  WandB tracking enabled")