"""
Build LoRA Adapters into Ollama Models
=======================================
Edit the CONFIG and ADAPTERS sections, then run:
    python build_models.py
"""

import subprocess
import sys
import os
import glob
import shutil
import time
from pathlib import Path

# ============================================================================
# CONFIG
# ============================================================================

BASE_MODEL_DIR = r"C:\Users\vipVi\gemma-3-4b-it"
LLAMA_CPP_DIR = r"C:\Users\vipVi\llama.cpp"
MERGE_WORKSPACE = r"C:\Users\vipVi\lora-merges"
QUANTIZE = "q8_0"  # None = F16, or "q4_K_M", "q8_0", etc.

# ============================================================================
# ADAPTERS — add your adapter folders here
#   "path":  full path to the adapter folder
#   The model name is derived from the last folder in the path automatically.
#   e.g. ...\Game-1_LORA\Smithing_4  →  ollama model name: "Smithing_4"
#
#   Optional: include "name" to override the auto-derived name.
# ============================================================================

ADAPTERS = [
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\New_Refining_1"},
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\New_Alchemy_1"},
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\Smithing_4"},
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\Adornment_2"},
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\New_Engineering_1"},
]
# ============================================================================
# Script — no need to edit below
# ============================================================================


def log(msg, level="INFO"):
    icons = {"INFO": "→", "OK": "✓", "FAIL": "✗", "WARN": "!", "STEP": "▸"}
    print(f"  {icons.get(level, ' ')} {msg}")


def run(cmd, cwd=None):
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Command failed: {' '.join(cmd[:3])}...\n{detail}")
    return result


def get_model_name(adapter):
    """Derive model name from the last folder in the path, or use explicit name."""
    if "name" in adapter:
        return adapter["name"]
    return Path(adapter["path"]).name


def get_existing_models():
    """Return a set of model names currently in Ollama."""
    try:
        result = run(["ollama", "list"])
        models = set()
        for line in result.stdout.strip().splitlines()[1:]:  # skip header
            parts = line.split()
            if parts:
                # Store both the full "name:tag" and just the name (without :latest)
                full = parts[0]
                models.add(full)
                models.add(full.split(":")[0])
        return models
    except RuntimeError:
        return set()


def preflight():
    print("\n  Preflight Checks")
    print("  " + "=" * 50)
    errors = []

    for pkg in ["peft", "transformers", "torch", "accelerate", "sentencepiece"]:
        try:
            __import__(pkg)
            log(f"{pkg}", "OK")
        except ImportError:
            log(f"{pkg} — missing", "FAIL")
            errors.append(pkg)

    if not Path(BASE_MODEL_DIR).is_dir():
        log(f"Base model not found: {BASE_MODEL_DIR}", "FAIL")
        errors.append("base model")

    if not (Path(LLAMA_CPP_DIR) / "convert_hf_to_gguf.py").is_file():
        log(f"convert_hf_to_gguf.py not found in {LLAMA_CPP_DIR}", "FAIL")
        errors.append("llama.cpp converter")

    try:
        run(["ollama", "--version"])
        log("Ollama CLI", "OK")
    except (FileNotFoundError, RuntimeError):
        log("Ollama not in PATH", "FAIL")
        errors.append("ollama")

    for a in ADAPTERS:
        name = get_model_name(a)
        p = Path(a["path"])
        missing = []
        if not (p / "adapter_model.safetensors").is_file():
            missing.append("adapter_model.safetensors")
        if not (p / "adapter_config.json").is_file():
            missing.append("adapter_config.json")
        if missing:
            log(f"'{name}': missing {', '.join(missing)}", "FAIL")
            errors.append(name)
        else:
            log(f"'{name}': {p}", "OK")

    if errors:
        print(f"\n  ✗ Fix these before running: {', '.join(errors)}")
        sys.exit(1)
    log("All checks passed\n", "OK")


def merge_lora(adapter_path, output_dir):
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    log("Loading base model...")
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_DIR, torch_dtype=torch.float16, low_cpu_mem_usage=True
    )
    log("Applying LoRA adapter...")
    model = PeftModel.from_pretrained(base, adapter_path)
    log("Merging weights...")
    merged = model.merge_and_unload()
    log(f"Saving merged model → {output_dir}")
    merged.save_pretrained(output_dir)

    log("Saving tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(adapter_path)
    tokenizer.save_pretrained(output_dir)

    # Ensure tokenizer.model gets copied (PEFT sometimes skips it)
    tok_src = Path(adapter_path) / "tokenizer.model"
    tok_dst = Path(output_dir) / "tokenizer.model"
    if tok_src.is_file() and not tok_dst.is_file():
        shutil.copy2(tok_src, tok_dst)
        log("Copied tokenizer.model manually", "WARN")

    del merged, model, base
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def convert_to_gguf(merged_dir):
    converter = str(Path(LLAMA_CPP_DIR) / "convert_hf_to_gguf.py")
    log("Converting to GGUF...")
    run([sys.executable, converter, merged_dir], cwd=merged_dir)

    gguf_files = glob.glob(os.path.join(merged_dir, "*.gguf"))
    if not gguf_files:
        raise RuntimeError("No .gguf file produced")
    gguf_path = max(gguf_files, key=os.path.getmtime)
    size_gb = os.path.getsize(gguf_path) / (1024 ** 3)
    log(f"GGUF: {Path(gguf_path).name} ({size_gb:.1f} GB)", "OK")
    return gguf_path


def import_to_ollama(model_name, gguf_path):
    modelfile = str(Path(gguf_path).parent / "Modelfile")
    with open(modelfile, "w", encoding="utf-8") as f:
        f.write(f"FROM ./{Path(gguf_path).name}\n")

    # Remove old version if re-running
    try:
        run(["ollama", "rm", model_name])
        log(f"Removed old '{model_name}'", "WARN")
    except RuntimeError:
        pass

    cmd = ["ollama", "create", model_name, "-f", modelfile]
    if QUANTIZE:
        cmd += ["--quantize", QUANTIZE]
        log(f"Importing with quantize={QUANTIZE}...")
    else:
        log("Importing (F16)...")

    run(cmd)
    log(f"ollama model '{model_name}' ready", "OK")


def build_one(adapter):
    name = get_model_name(adapter)
    adapter_path = adapter["path"]
    merged_dir = str(Path(MERGE_WORKSPACE) / f"{name}-merged")

    print(f"\n{'=' * 60}")
    print(f"  Building: {name}")
    print(f"  Adapter:  {adapter_path}")
    print(f"{'=' * 60}")

    try:
        os.makedirs(merged_dir, exist_ok=True)

        t0 = time.time()
        log("STEP 1/3 — Merge", "STEP")
        merge_lora(adapter_path, merged_dir)
        log(f"Merge: {time.time() - t0:.0f}s")

        t1 = time.time()
        log("STEP 2/3 — Convert to GGUF", "STEP")
        gguf_path = convert_to_gguf(merged_dir)
        log(f"Convert: {time.time() - t1:.0f}s")

        t2 = time.time()
        log("STEP 3/3 — Import to Ollama", "STEP")
        import_to_ollama(name, gguf_path)
        log(f"Import: {time.time() - t2:.0f}s")

        log(f"Total: {time.time() - t0:.0f}s", "OK")
        return True

    except Exception as e:
        log(f"FAILED: {e}", "FAIL")
        return False

    finally:
        if os.path.isdir(merged_dir):
            shutil.rmtree(merged_dir, ignore_errors=True)
            log("Cleaned up merge workspace")


def main():
    print(f"\n  LoRA → Ollama Builder")
    print(f"  Models: {len(ADAPTERS)} | Quantize: {QUANTIZE or 'F16'}")

    preflight()
    os.makedirs(MERGE_WORKSPACE, exist_ok=True)

    # Check which models already exist
    existing = get_existing_models()

    results = {}
    for adapter in ADAPTERS:
        name = get_model_name(adapter)
        if name in existing:
            log(f"'{name}' already exists in Ollama — skipping", "OK")
            results[name] = True
            continue
        results[name] = build_one(adapter)

    # Cleanup workspace
    try:
        os.rmdir(MERGE_WORKSPACE)
    except OSError:
        pass

    # Summary
    print(f"\n{'=' * 60}")
    print("  Results")
    print(f"{'=' * 60}")
    for name, ok in results.items():
        skipped = name in existing
        tag = "✓ (skipped)" if (ok and skipped) else ("✓" if ok else "✗")
        print(f"  {tag} {name}")
    print(f"\n  Run a model:  ollama run <name>")

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()