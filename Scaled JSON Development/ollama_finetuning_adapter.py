"""
Build LoRA Adapters into Ollama Models
=======================================
Edit the CONFIG and ADAPTERS sections, then run:
    python build_models.py

Vision models:  convert LoRA → GGUF adapter, layer on top of gemma3:4b (keeps vision)
Text models:    merge LoRA into base, convert to GGUF, import standalone
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

# Ollama base model that has vision support (used for vision adapters)
OLLAMA_VISION_BASE = "gemma3:4b"

# ============================================================================
# ADAPTERS
#   "path":   full path to the adapter folder
#   "vision": True → uses ADAPTER approach on top of gemma3:4b (preserves vision)
#             False/omitted → merges into base model (text-only, standalone)
# ============================================================================

ADAPTERS = [
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\New_Refining_1"},
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\New_Alchemy_1"},
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\Smithing_4",       "vision": True},
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\Adornment_2",      "vision": True},
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\New_Engineering_1"},
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\Smithing_5", "vision": True}
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\Smithing_6",       "vision": True},
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\Adornment_2a",      "vision": True},
    {"path": r"C:\Users\vipVi\Downloads\Game-1_LORA\Smithing_7", "vision": True}
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
    if "name" in adapter:
        return adapter["name"]
    return Path(adapter["path"]).name


def get_existing_models():
    try:
        result = run(["ollama", "list"])
        models = set()
        for line in result.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if parts:
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

    for pkg in ["peft", "transformers", "torch", "accelerate", "sentencepiece", "safetensors"]:
        try:
            __import__(pkg)
            log(f"{pkg}", "OK")
        except ImportError:
            log(f"{pkg} — missing", "FAIL")
            errors.append(pkg)

    if not Path(BASE_MODEL_DIR).is_dir():
        log(f"Base model not found: {BASE_MODEL_DIR}", "FAIL")
        errors.append("base model")
    else:
        # Check if base model has vision weights (needed for vision adapters)
        has_vision_adapters = any(a.get("vision") for a in ADAPTERS)
        if has_vision_adapters:
            config_path = Path(BASE_MODEL_DIR) / "config.json"
            has_vision_config = False
            if config_path.is_file():
                import json as _json
                with open(config_path) as _f:
                    cfg = _json.load(_f)
                has_vision_config = (
                    "vision_config" in cfg
                    or "model_type" in cfg and "vlm" in cfg.get("model_type", "").lower()
                    or any("vision" in str(k).lower() for k in cfg.keys())
                )
            if has_vision_config:
                log(f"Base model has vision config", "OK")
            else:
                log(f"Base model may lack vision weights!", "WARN")
                log(f"Your adapters were trained on togethercomputer/gemma-3-4b-it-VLM", "WARN")
                log(f"Ensure BASE_MODEL_DIR points to the VLM variant", "WARN")

    if not (Path(LLAMA_CPP_DIR) / "convert_hf_to_gguf.py").is_file():
        log(f"convert_hf_to_gguf.py not found in {LLAMA_CPP_DIR}", "FAIL")
        errors.append("llama.cpp converter")

    # Check LoRA converter exists (needed for vision models)
    lora_converter = Path(LLAMA_CPP_DIR) / "convert_lora_to_gguf.py"
    if not lora_converter.is_file():
        has_vision = any(a.get("vision") for a in ADAPTERS)
        if has_vision:
            log(f"convert_lora_to_gguf.py not found in {LLAMA_CPP_DIR}", "FAIL")
            errors.append("llama.cpp lora converter")
        else:
            log("convert_lora_to_gguf.py not found (not needed, no vision adapters)", "WARN")

    try:
        run(["ollama", "--version"])
        log("Ollama CLI", "OK")
    except (FileNotFoundError, RuntimeError):
        log("Ollama not in PATH", "FAIL")
        errors.append("ollama")

    # Verify vision base model exists in Ollama
    has_vision = any(a.get("vision") for a in ADAPTERS)
    if has_vision:
        existing = get_existing_models()
        base_name = OLLAMA_VISION_BASE.split(":")[0]
        if base_name in existing or OLLAMA_VISION_BASE in existing:
            log(f"Vision base '{OLLAMA_VISION_BASE}' in Ollama", "OK")
        else:
            log(f"Vision base '{OLLAMA_VISION_BASE}' not found — run: ollama pull {OLLAMA_VISION_BASE}", "FAIL")
            errors.append("vision base model")

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
            tag = " [vision]" if a.get("vision") else " [text]"
            log(f"'{name}'{tag}: {p}", "OK")

    if errors:
        print(f"\n  ✗ Fix these before running: {', '.join(errors)}")
        sys.exit(1)
    log("All checks passed\n", "OK")


# ── Vision path: merge LoRA, let Ollama convert safetensors (preserves vision) ─

def merge_lora_vision(adapter_path, output_dir):
    """Merge LoRA into the full vision model (not just CausalLM)."""
    import torch
    from peft import PeftModel
    from transformers import AutoTokenizer, AutoProcessor

    # Try vision-aware model classes in order of preference
    model_cls = None
    import transformers
    for cls_name in ["AutoModelForImageTextToText", "AutoModelForVision2Seq", "AutoModel"]:
        if hasattr(transformers, cls_name):
            model_cls = getattr(transformers, cls_name)
            log(f"Using model class: {cls_name}")
            break

    if model_cls is None:
        raise RuntimeError("Could not find a vision-capable model class in transformers. Update: pip install -U transformers")

    log("Loading base model (with vision tower)...")
    base = model_cls.from_pretrained(
        BASE_MODEL_DIR, torch_dtype=torch.float16, low_cpu_mem_usage=True
    )
    log("Applying LoRA adapter...")
    model = PeftModel.from_pretrained(base, adapter_path)
    log("Merging weights...")
    merged = model.merge_and_unload()
    log(f"Saving merged model → {output_dir}")
    merged.save_pretrained(output_dir)

    log("Saving tokenizer/processor...")
    try:
        processor = AutoProcessor.from_pretrained(BASE_MODEL_DIR)
        processor.save_pretrained(output_dir)
        log("Saved processor", "OK")
    except Exception:
        tokenizer = AutoTokenizer.from_pretrained(adapter_path)
        tokenizer.save_pretrained(output_dir)
        log("Saved tokenizer (no processor found)", "WARN")

    # Copy tokenizer.model if missing
    for src_dir in [adapter_path, BASE_MODEL_DIR]:
        tok_src = Path(src_dir) / "tokenizer.model"
        tok_dst = Path(output_dir) / "tokenizer.model"
        if tok_src.is_file() and not tok_dst.is_file():
            shutil.copy2(tok_src, tok_dst)
            log("Copied tokenizer.model", "WARN")
            break

    del merged, model, base
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def build_vision(adapter):
    """Merge LoRA into full vision model, import safetensors directly into Ollama.

    Ollama's internal Gemma 3 converter preserves vision when importing from
    safetensors. External GGUF conversion loses the vision projector.
    """
    name = get_model_name(adapter)
    adapter_path = adapter["path"]
    merged_dir = str(Path(MERGE_WORKSPACE) / f"{name}-merged")

    print(f"\n{'=' * 60}")
    print(f"  Building (VISION): {name}")
    print(f"  Strategy: merge → safetensors → ollama create (no GGUF)")
    print(f"  Adapter:  {adapter_path}")
    print(f"  Base:     {BASE_MODEL_DIR}")
    print(f"{'=' * 60}")

    try:
        os.makedirs(merged_dir, exist_ok=True)

        t0 = time.time()
        log("STEP 1/2 — Merge (vision-aware)", "STEP")
        merge_lora_vision(adapter_path, merged_dir)
        log(f"Merge: {time.time() - t0:.0f}s")

        t1 = time.time()
        log("STEP 2/2 — Import safetensors to Ollama (vision preserved)", "STEP")

        # Create Modelfile pointing at the safetensors directory
        modelfile = str(Path(merged_dir) / "Modelfile")
        with open(modelfile, "w", encoding="utf-8") as f:
            f.write(f"FROM {merged_dir}\n")
        log(f"Modelfile: FROM {merged_dir}")

        # Remove old version
        try:
            run(["ollama", "rm", name])
            log(f"Removed old '{name}'", "WARN")
        except RuntimeError:
            pass

        # Import — Ollama converts safetensors internally, preserving vision
        cmd = ["ollama", "create", name, "-f", modelfile]
        if QUANTIZE:
            cmd += ["--quantize", QUANTIZE]
            log(f"Importing with quantize={QUANTIZE}...")
        else:
            log("Importing (F16)...")

        run(cmd)
        log(f"Import: {time.time() - t1:.0f}s")

        # Verify vision
        try:
            result = run(["ollama", "show", name])
            if "vision" in result.stdout.lower():
                log(f"'{name}' — vision confirmed", "OK")
            else:
                log(f"'{name}' — vision NOT detected!", "WARN")
                log("Check that your base model has vision weights", "WARN")
        except RuntimeError:
            pass

        log(f"Total: {time.time() - t0:.0f}s", "OK")
        return True

    except Exception as e:
        log(f"FAILED: {e}", "FAIL")
        return False

    finally:
        if os.path.isdir(merged_dir):
            shutil.rmtree(merged_dir, ignore_errors=True)
            log("Cleaned up merge workspace")


# ── Text path: merge LoRA into base, convert full model ────────────────────

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


def build_text(adapter):
    """Merge LoRA into base, convert to GGUF, import standalone."""
    name = get_model_name(adapter)
    adapter_path = adapter["path"]
    merged_dir = str(Path(MERGE_WORKSPACE) / f"{name}-merged")

    print(f"\n{'=' * 60}")
    print(f"  Building (TEXT): {name}")
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


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    vision_count = sum(1 for a in ADAPTERS if a.get("vision"))
    text_count = len(ADAPTERS) - vision_count
    print(f"\n  LoRA → Ollama Builder")
    print(f"  Models: {len(ADAPTERS)} ({vision_count} vision, {text_count} text) | Quantize: {QUANTIZE or 'F16'}")

    preflight()
    os.makedirs(MERGE_WORKSPACE, exist_ok=True)

    existing = get_existing_models()

    results = {}
    for adapter in ADAPTERS:
        name = get_model_name(adapter)
        if name in existing:
            log(f"'{name}' already exists in Ollama — skipping", "OK")
            results[name] = True
            continue

        if adapter.get("vision"):
            results[name] = build_vision(adapter)
        else:
            results[name] = build_text(adapter)

    try:
        os.rmdir(MERGE_WORKSPACE)
    except OSError:
        pass

    print(f"\n{'=' * 60}")
    print("  Results")
    print(f"{'=' * 60}")
    for name, ok in results.items():
        skipped = name in existing
        tag = "✓ (skipped)" if (ok and skipped) else ("✓" if ok else "✗")
        vision_tag = ""
        for a in ADAPTERS:
            if get_model_name(a) == name and a.get("vision"):
                vision_tag = " [vision]"
        print(f"  {tag} {name}{vision_tag}")
    print(f"\n  Run a model:  ollama run <name>")

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()