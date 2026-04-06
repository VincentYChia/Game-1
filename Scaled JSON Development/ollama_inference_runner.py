"""
Ollama Inference Script
========================
Send prompts to your Ollama models with full control over parameters.
Edit the REQUEST section below, then run:
    python inference.py
"""

import json
import base64
import urllib.request
import sys
from pathlib import Path

# ============================================================================
# REQUEST — edit this for each inference call
# ============================================================================

MODEL = "New_Engineering_1"

SYSTEM_PROMPT = "You are a helpful assistant."

PROMPT = "Hello, tell me some things about yourself. What are you knowledegable about."

# Image path — set to None if not using vision, or a path to an image file
IMAGE = None
# IMAGE = r"C:\Users\vipVi\some_image.png"

# ============================================================================
# PARAMETERS
# ============================================================================

TEMPERATURE = 0.7
TOP_P = 0.9
TOP_K = 40
MAX_TOKENS = 1024        # num_predict in Ollama
REPEAT_PENALTY = 1.1
SEED = None               # None = random, set int for reproducible output

# ============================================================================
# SETTINGS
# ============================================================================

OLLAMA_API = "http://localhost:11434"
STREAM = True             # True = print tokens as they arrive
SHOW_STATS = True         # Print timing/token stats after response

# ============================================================================
# Script — no need to edit below
# ============================================================================


def encode_image(image_path):
    """Read image file and return base64 string."""
    p = Path(image_path)
    if not p.is_file():
        print(f"  ✗ Image not found: {image_path}")
        sys.exit(1)
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def build_payload():
    payload = {
        "model": MODEL,
        "prompt": PROMPT,
        "system": SYSTEM_PROMPT,
        "stream": STREAM,
        "options": {
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "top_k": TOP_K,
            "num_predict": MAX_TOKENS,
            "repeat_penalty": REPEAT_PENALTY,
        },
    }
    if SEED is not None:
        payload["options"]["seed"] = SEED
    if IMAGE:
        payload["images"] = [encode_image(IMAGE)]
    return payload


def infer_stream(payload):
    """Stream tokens to stdout as they arrive."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_API}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    full_response = ""
    stats = {}

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            for line in resp:
                chunk = json.loads(line.decode("utf-8"))
                token = chunk.get("response", "")
                if token:
                    print(token, end="", flush=True)
                    full_response += token
                if chunk.get("done"):
                    stats = chunk
    except urllib.error.URLError as e:
        print(f"\n  ✗ Connection error: {e}")
        print("    Is Ollama running? Start it with: ollama serve")
        sys.exit(1)

    print()  # newline after streamed output
    return full_response, stats


def infer_blocking(payload):
    """Wait for full response, then print."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_API}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"\n  ✗ Connection error: {e}")
        print("    Is Ollama running? Start it with: ollama serve")
        sys.exit(1)

    response = result.get("response", "")
    print(response)
    return response, result


def print_stats(stats):
    """Print generation statistics."""
    if not stats:
        return
    print(f"\n  {'─' * 40}")
    prompt_tokens = stats.get("prompt_eval_count", 0)
    gen_tokens = stats.get("eval_count", 0)
    total_ns = stats.get("total_duration", 0)
    eval_ns = stats.get("eval_duration", 0)

    print(f"  Prompt tokens:  {prompt_tokens}")
    print(f"  Output tokens:  {gen_tokens}")
    if total_ns:
        print(f"  Total time:     {total_ns / 1e9:.2f}s")
    if eval_ns and gen_tokens:
        tok_per_sec = gen_tokens / (eval_ns / 1e9)
        print(f"  Speed:          {tok_per_sec:.1f} tok/s")


def main():
    print(f"\n  Model:   {MODEL}")
    print(f"  System:  {SYSTEM_PROMPT[:60]}{'...' if len(SYSTEM_PROMPT) > 60 else ''}")
    print(f"  Prompt:  {PROMPT[:60]}{'...' if len(PROMPT) > 60 else ''}")
    if IMAGE:
        print(f"  Image:   {IMAGE}")
    print(f"  Params:  temp={TEMPERATURE} top_p={TOP_P} top_k={TOP_K} max={MAX_TOKENS}")
    print(f"  {'─' * 40}")
    print()

    payload = build_payload()

    if STREAM:
        response, stats = infer_stream(payload)
    else:
        response, stats = infer_blocking(payload)

    if SHOW_STATS:
        print_stats(stats)


if __name__ == "__main__":
    main()