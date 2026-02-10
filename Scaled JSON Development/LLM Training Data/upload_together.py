#!/usr/bin/env python3
"""Upload JSONL file to Together.ai for fine-tuning."""

import os
from pathlib import Path
from together import Together

# Get script directory for relative paths
SCRIPT_DIR = Path(__file__).parent
JSONL_DIR = SCRIPT_DIR / "jsonl_outputs"

# Change this to the file you want to upload
FILE_TO_UPLOAD = JSONL_DIR / "adornment.jsonl"

client = Together(api_key=os.environ.get("TOGETHER_API_KEY"))

if not FILE_TO_UPLOAD.exists():
    print(f"Error: File not found: {FILE_TO_UPLOAD}")
    exit(1)

print(f"Uploading: {FILE_TO_UPLOAD}")
file_resp = client.files.upload(file=str(FILE_TO_UPLOAD), check=True)

print(file_resp.model_dump())