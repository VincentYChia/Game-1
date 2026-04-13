#!/usr/bin/env python3
"""Simple Together.ai File Upload Script"""

import os
import json
from together import Together

# ============================================================================
# CHANGE THIS
# ============================================================================

FILE_PATH = r"C:\Users\vipVi\PycharmProjects\Game-1\Scaled JSON Development\LLM Training Data\jsonl_outputs\adornment_train.jsonl"  # Your JSONL file to upload

# ============================================================================
# API KEY (from environment)
# ============================================================================

TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY")

if not TOGETHER_API_KEY:
    raise ValueError("TOGETHER_API_KEY environment variable not set")

# ============================================================================
# CHECK FILE
# ============================================================================

print(f"Checking file: {FILE_PATH}")

# Check if file exists
if not os.path.exists(FILE_PATH):
    raise FileNotFoundError(f"File not found: {FILE_PATH}")

# Basic JSONL validation
line_count = 0
with open(FILE_PATH, 'r') as f:
    for i, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
            line_count += 1
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON on line {i}: {e}")

print(f"✓ File valid: {line_count} examples found")

# ============================================================================
# UPLOAD FILE
# ============================================================================

print(f"\nUploading to Together.ai...")

client = Together(api_key=TOGETHER_API_KEY)

response = client.files.upload(file=FILE_PATH)

print(f"✓ Upload complete!")
print(f"\nFILE_ID = \"{response.id}\"")
print(f"\nFile details:")
print(f"  ID: {response.id}")
print(f"  Filename: {response.filename}")
print(f"  Purpose: {response.purpose}")
print(f"  Created: {response.created_at}")