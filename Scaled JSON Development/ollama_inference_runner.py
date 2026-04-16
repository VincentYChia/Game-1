"""
Ollama Inference Runner — Web UI
=================================
A local web interface for testing fine-tuned Ollama models against training data.

Install:  pip install flask
Run:      python ollama_inference_runner.py
Open:     http://localhost:5111
"""

import json
import base64
import urllib.request
import os
import glob
import sys
import threading
from pathlib import Path
from flask import Flask, jsonify, request, Response, stream_with_context

# ============================================================================
# CONFIGURATION — edit these paths to match your setup
# ============================================================================

MODEL_MAP = {
    "smithing":    "Smithing_4",
    "alchemy":     "New_Alchemy_1",
    "refining":    "New_Refining_1",
    "adornment":   "Adornment_2",
    "engineering": "New_Engineering_1",
}

JSONL_DIR = r"C:\Users\vipVi\PycharmProjects\Game-1\Scaled JSON Development\LLM Training Data\jsonl_outputs"
SYSTEM_PROMPT_DIR = r"C:\Users\vipVi\PycharmProjects\Game-1\Scaled JSON Development\LLM Training Data\Synthetic_Training\system_prompts"

# Live (few-shot) system prompts — numbered files mapped to disciplines
LIVE_PROMPT_DIR = r"C:\Users\vipVi\PycharmProjects\Game-1\Scaled JSON Development\LLM Training Data\Fewshot_llm\prompts\system_prompts"
LIVE_PROMPT_MAP = {
    "smithing":    "system_1.txt",
    "refining":    "system_2.txt",
    "alchemy":     "system_3.txt",
    "engineering": "system_4.txt",
    "adornment":   "system_5.txt",
}

OLLAMA_API = "http://localhost:11434"

# JSON validator — set this to the path of json_validator.py
VALIDATOR_PATH = r"C:\Users\vipVi\PycharmProjects\Game-1\Scaled JSON Development\json_validator.py"

# ============================================================================
# Flask app
# ============================================================================

app = Flask(__name__)


def get_disciplines():
    """Scan JSONL dir — only return base files (no _train/_validation splits)."""
    discs = {}
    pattern = os.path.join(JSONL_DIR, "*.jsonl")
    for fp in sorted(glob.glob(pattern)):
        name = Path(fp).stem
        if "_train" in name or "_validation" in name:
            continue
        discs[name] = fp
    return discs


def load_jsonl(filepath, limit=None):
    entries = []
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def load_system_prompt(discipline, mode="training"):
    """Load a system prompt.

    mode="training"  → original prompts from SYSTEM_PROMPT_DIR
    mode="live"      → few-shot prompts from LIVE_PROMPT_DIR
    """
    base = discipline.split("_")[0].lower()
    print(f"  [prompt] discipline='{discipline}' base='{base}' mode='{mode}'", flush=True)

    if mode == "live":
        filename = LIVE_PROMPT_MAP.get(base)
        print(f"  [prompt] LIVE_PROMPT_MAP.get('{base}') → '{filename}'", flush=True)
        if filename:
            fp = os.path.join(LIVE_PROMPT_DIR, filename)
            exists = os.path.isfile(fp)
            print(f"  [prompt] live path: {fp}  exists={exists}", flush=True)
            if exists:
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                print(f"  [prompt] ✓ LOADED LIVE prompt ({len(content)} chars)", flush=True)
                return content
        print(f"  [prompt] ⚠ Live prompt not found for '{base}', falling back to training", flush=True)

    # Training mode (or fallback)
    for name in [discipline, base]:
        fp = os.path.join(SYSTEM_PROMPT_DIR, f"{name}.txt")
        if os.path.isfile(fp):
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read().strip()
            print(f"  [prompt] ✓ LOADED TRAINING prompt from {fp} ({len(content)} chars)", flush=True)
            return content
    print(f"  [prompt] ⚠ No prompt found at all, using default", flush=True)
    return "You are a helpful assistant."


def detect_model(discipline):
    base = discipline.split("_")[0].lower()
    return MODEL_MAP.get(base, list(MODEL_MAP.values())[0])


def extract_prompt_and_image(entry):
    prompt_parts = entry.get("prompt", [])
    text = ""
    image_b64 = None
    for part in prompt_parts:
        if part.get("type") == "text":
            text = part.get("text", "")
        elif part.get("type") == "image_url":
            url = part.get("image_url", {}).get("url", "")
            if url.startswith("data:") and "," in url:
                image_b64 = url.split(",", 1)[1]
            else:
                image_b64 = url
    return text, image_b64


def extract_completion(entry):
    comp = entry.get("completion", [])
    for part in comp:
        if part.get("type") == "text":
            return part.get("text", "")
    return ""


@app.route("/api/disciplines")
def api_disciplines():
    discs = get_disciplines()
    result = []
    for name, path in discs.items():
        base = name.split("_")[0].lower()
        result.append({"name": name, "path": path, "model": detect_model(name), "base": base})
    return jsonify(result)


@app.route("/api/entries")
def api_entries():
    filepath = request.args.get("file", "")
    if not filepath or not os.path.isfile(filepath):
        return jsonify({"error": "File not found"}), 404
    entries = load_jsonl(filepath)
    summaries = []
    for i, e in enumerate(entries):
        text, img = extract_prompt_and_image(e)
        label = ""
        for line in text.split("\n"):
            if line.strip().startswith("Recipe:") or line.strip().startswith("Station:"):
                label = line.strip()
                break
        if not label:
            label = text[:80]
        summaries.append({"index": i, "label": label, "has_image": img is not None})
    return jsonify({"count": len(entries), "entries": summaries})


@app.route("/api/entry")
def api_entry():
    filepath = request.args.get("file", "")
    idx = int(request.args.get("index", 0))
    if not filepath or not os.path.isfile(filepath):
        return jsonify({"error": "File not found"}), 404
    entries = load_jsonl(filepath)
    if idx >= len(entries):
        return jsonify({"error": f"Index {idx} out of range ({len(entries)})"}), 400
    entry = entries[idx]
    text, img = extract_prompt_and_image(entry)
    expected = extract_completion(entry)
    return jsonify({"prompt_text": text, "image_base64": img, "expected_completion": expected})


@app.route("/api/infer", methods=["POST"])
def api_infer():
    body = request.json
    payload = {
        "model": body.get("model", ""),
        "prompt": body.get("prompt", ""),
        "system": body.get("system", ""),
        "stream": True,
        "options": {
            "temperature": body.get("temperature", 0.7),
            "top_p": body.get("top_p", 0.9),
            "top_k": body.get("top_k", 40),
            "num_predict": body.get("max_tokens", 2048),
            "repeat_penalty": body.get("repeat_penalty", 1.1),
        },
    }
    if body.get("seed") is not None:
        payload["options"]["seed"] = body["seed"]
    if body.get("image"):
        payload["images"] = [body["image"]]

    def generate():
        print(f"  → Infer: model={payload['model']}  system_len={len(payload.get('system',''))}  system_first80={payload.get('system','')[:80]!r}", flush=True)
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_API}/api/generate", data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                for line in resp:
                    chunk = json.loads(line.decode("utf-8"))
                    token = chunk.get("response", "")
                    done = chunk.get("done", False)
                    stats = {}
                    if done:
                        stats = {
                            "prompt_tokens": chunk.get("prompt_eval_count", 0),
                            "output_tokens": chunk.get("eval_count", 0),
                            "total_duration": chunk.get("total_duration", 0),
                            "eval_duration": chunk.get("eval_duration", 0),
                        }
                    yield f"data: {json.dumps({'token': token, 'done': done, 'stats': stats})}\n\n"
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            msg = f"Ollama HTTP {e.code}: {detail or e.reason}"
            print(f"  ✗ {msg}", flush=True)
            yield f"data: {json.dumps({'error': msg, 'done': True, 'stats': {}})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True, 'stats': {}})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/api/system_prompt")
def api_system_prompt():
    discipline = request.args.get("discipline", "")
    mode = request.args.get("mode", "training")
    print(f"  [api] /api/system_prompt?discipline='{discipline}' mode='{mode}'", flush=True)
    prompt = load_system_prompt(discipline, mode)
    print(f"  [api] returning prompt: {len(prompt)} chars, first 80: {prompt[:80]!r}", flush=True)
    return jsonify({"prompt": prompt, "mode": mode})


@app.route("/api/models")
def api_models():
    try:
        req = urllib.request.Request(f"{OLLAMA_API}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        names = [m["name"] for m in data.get("models", [])]
        return jsonify({"models": names})
    except Exception as e:
        return jsonify({"models": [], "error": str(e)})


# ── Validator ───────────────────────────────────────────────────────────────

_validator_module = None

def _get_validator():
    """Dynamically import json_validator.py"""
    global _validator_module
    if _validator_module is not None:
        return _validator_module
    if not os.path.isfile(VALIDATOR_PATH):
        print(f"  [validator] ⚠ Not found: {VALIDATOR_PATH}", flush=True)
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("json_validator", VALIDATOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _validator_module = mod
    print(f"  [validator] ✓ Loaded from {VALIDATOR_PATH}", flush=True)
    return mod


# Map discipline → validator method name
DISCIPLINE_VALIDATOR = {
    "smithing":    "_validate_recipes",
    "alchemy":     "_validate_recipes",
    "refining":    "_validate_recipes",
    "engineering": "_validate_recipes",
    "adornment":   "_validate_recipes",
}


@app.route("/api/validate", methods=["POST"])
def api_validate():
    body = request.json
    raw_json = body.get("json_text", "")
    discipline = body.get("discipline", "").lower()
    expected_json = body.get("expected_text", "")

    results = {"errors": [], "warnings": [], "valid": False, "json_parsed": False}

    # Step 1: parse JSON
    try:
        parsed = json.loads(raw_json)
        results["json_parsed"] = True
    except json.JSONDecodeError as e:
        results["errors"].append(f"JSON parse error: {e}")
        return jsonify(results)

    # Step 2: structural validation via validator
    mod = _get_validator()
    if mod:
        try:
            validator = mod.GameJSONValidator()
            method_name = DISCIPLINE_VALIDATOR.get(discipline, "_validate_recipes")
            method = getattr(validator, method_name, None)

            if method and isinstance(parsed, dict):
                # Wrap single recipe in expected structure if needed
                if 'recipes' not in parsed and 'recipeId' in parsed:
                    wrapped = {"recipes": [parsed]}
                elif 'recipes' not in parsed and isinstance(parsed, dict):
                    # Try to detect: might be a full file already
                    wrapped = parsed
                else:
                    wrapped = parsed
                errs = method(wrapped, "<model_output>")
                for e in errs:
                    results["errors"].append(e)
            elif method and isinstance(parsed, list):
                # Array of recipes
                wrapped = {"recipes": parsed}
                errs = method(wrapped, "<model_output>")
                for e in errs:
                    results["errors"].append(e)
        except Exception as e:
            results["warnings"].append(f"Validator error: {e}")

    # Step 3: compare structure with expected (if provided)
    if expected_json:
        try:
            expected = json.loads(expected_json)
            # Key-level comparison
            if isinstance(parsed, dict) and isinstance(expected, dict):
                missing_keys = set(expected.keys()) - set(parsed.keys())
                extra_keys = set(parsed.keys()) - set(expected.keys())
                if missing_keys:
                    results["warnings"].append(f"Missing keys vs expected: {', '.join(sorted(missing_keys))}")
                if extra_keys:
                    results["warnings"].append(f"Extra keys vs expected: {', '.join(sorted(extra_keys))}")
        except:
            pass

    results["valid"] = len(results["errors"]) == 0
    print(f"  [validate] discipline={discipline} parsed={results['json_parsed']} "
          f"errors={len(results['errors'])} warnings={len(results['warnings'])}", flush=True)
    return jsonify(results)


# ── HTML UI ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return HTML_PAGE


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ollama Inference Runner</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Libre+Franklin:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #f5f5f0;
  --bg2: #ffffff;
  --bg3: #eeeee8;
  --bg4: #e4e4dc;
  --border: #d4d4cc;
  --border-hi: #b8b8b0;
  --text: #2c2c28;
  --text2: #6a6a60;
  --text3: #9a9a90;
  --accent: #3566d6;
  --accent2: #2850b0;
  --accent-light: rgba(53,102,214,0.08);
  --green: #1a8a4a;
  --green-bg: rgba(26,138,74,0.07);
  --red: #cc3344;
  --orange: #c07a10;
  --orange-bg: rgba(192,122,16,0.07);
  --mono: 'JetBrains Mono', monospace;
  --sans: 'Libre Franklin', system-ui, sans-serif;
  --radius: 6px;
  --shadow: 0 1px 3px rgba(0,0,0,0.06);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 14px; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
  min-height: 100vh;
}
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

.app { display: flex; height: 100vh; }

/* Sidebar */
.sidebar {
  width: 300px; min-width: 300px;
  background: var(--bg2);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  box-shadow: var(--shadow);
}
.sidebar-header {
  padding: 20px 16px 14px;
  border-bottom: 1px solid var(--border);
}
.logo {
  font-family: var(--mono);
  font-weight: 700; font-size: 0.95rem;
  color: var(--accent);
  letter-spacing: -0.02em;
}
.logo-sub { font-size: 0.72rem; color: var(--text3); margin-top: 2px; }
.sidebar-section { padding: 12px 16px 8px; }
.sidebar-section label {
  display: block; font-size: 0.68rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--text3); margin-bottom: 5px;
}
select, input[type="number"] {
  width: 100%; background: var(--bg2);
  border: 1px solid var(--border); color: var(--text);
  font-family: var(--mono); font-size: 0.8rem;
  padding: 7px 10px; border-radius: var(--radius);
  outline: none; transition: border-color 0.15s;
}
select:focus, input:focus { border-color: var(--accent); }
select option { background: var(--bg2); }

/* Prompt mode toggle */
.prompt-toggle {
  display: flex; border-radius: var(--radius); overflow: hidden;
  border: 1px solid var(--border);
}
.prompt-toggle-btn {
  flex: 1; padding: 6px 0; text-align: center;
  font-family: var(--mono); font-size: 0.72rem; font-weight: 600;
  cursor: pointer; border: none; background: var(--bg2);
  color: var(--text3); transition: all 0.15s;
}
.prompt-toggle-btn:first-child { border-right: 1px solid var(--border); }
.prompt-toggle-btn.active {
  background: var(--accent); color: #fff;
}
.prompt-toggle-btn:not(.active):hover {
  background: var(--bg3); color: var(--text2);
}

.entry-list { flex: 1; overflow-y: auto; border-top: 1px solid var(--border); }
.entry-item {
  padding: 7px 16px; font-size: 0.73rem; font-family: var(--mono);
  color: var(--text2); cursor: pointer;
  border-bottom: 1px solid var(--bg3);
  transition: background 0.1s;
  display: flex; align-items: center; gap: 8px;
}
.entry-item:hover { background: var(--bg3); }
.entry-item.active {
  background: var(--accent-light); color: var(--accent);
  border-left: 2px solid var(--accent);
}
.entry-idx { font-size: 0.63rem; color: var(--text3); min-width: 28px; text-align: right; }
.entry-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.entry-img-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); flex-shrink: 0; }

.main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

/* Top bar */
.topbar {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--bg2);
}
.model-badge {
  font-family: var(--mono); font-size: 0.78rem; font-weight: 700;
  color: var(--green); background: var(--green-bg);
  padding: 3px 12px; border-radius: 20px;
}
.mode-badge {
  font-family: var(--mono); font-size: 0.72rem; font-weight: 600;
  padding: 3px 10px; border-radius: 20px;
}
.mode-badge.training {
  color: var(--accent); background: var(--accent-light);
}
.mode-badge.live {
  color: var(--orange); background: var(--orange-bg);
}
.topbar-info { font-size: 0.73rem; color: var(--text3); }
.spacer { flex: 1; }

.btn {
  font-family: var(--sans); font-weight: 600; font-size: 0.8rem;
  border: none; padding: 7px 18px; border-radius: var(--radius);
  cursor: pointer; transition: all 0.15s;
}
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { background: var(--accent2); }
.btn-primary:disabled { opacity: 0.35; cursor: default; }
.btn-ghost { background: transparent; color: var(--text2); border: 1px solid var(--border); }
.btn-ghost:hover { border-color: var(--text2); color: var(--text); }

.config-bar {
  display: flex; gap: 12px; align-items: center;
  padding: 7px 20px; border-bottom: 1px solid var(--border);
  background: var(--bg3); flex-wrap: wrap;
}
.config-bar label {
  font-size: 0.68rem; color: var(--text3); font-family: var(--mono);
  display: flex; align-items: center; gap: 4px;
}
.config-bar input[type="number"] {
  width: 68px; padding: 3px 6px; font-size: 0.73rem; background: var(--bg2);
}

.content { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 14px; }

.panel {
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow);
}
.panel-header {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 14px; border-bottom: 1px solid var(--border);
  background: var(--bg3);
}
.panel-title {
  font-size: 0.68rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.08em; color: var(--text3);
}
.panel-dot { width: 6px; height: 6px; border-radius: 50%; }
.panel-body {
  padding: 14px; font-family: var(--mono); font-size: 0.76rem;
  line-height: 1.6; white-space: pre-wrap; word-break: break-word;
  color: var(--text); max-height: 400px; overflow-y: auto;
}
.compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

.image-preview {
  display: flex; align-items: center; justify-content: center;
  padding: 12px; background: var(--bg3); border-radius: var(--radius);
  border: 1px solid var(--border);
}
.image-preview img {
  image-rendering: pixelated; width: 256px; height: 256px;
  border: 1px solid var(--border); border-radius: 4px;
}

.stats-bar {
  display: flex; gap: 20px; padding: 8px 14px;
  font-family: var(--mono); font-size: 0.7rem; color: var(--text3);
  border-top: 1px solid var(--border); background: var(--bg3);
}
.stat-val { color: var(--text); font-weight: 600; }

.spinner {
  display: inline-block; width: 13px; height: 13px;
  border: 2px solid var(--border); border-top-color: var(--accent);
  border-radius: 50%; animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 100%;
  color: var(--text3); font-size: 0.85rem; gap: 8px;
}
.empty-icon { font-size: 2.5rem; opacity: 0.3; }

@media (max-width: 900px) {
  .compare-grid { grid-template-columns: 1fr; }
  .sidebar { width: 240px; min-width: 240px; }
}

/* System prompt modal */
.modal-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center;
  animation: fadeIn 0.15s ease;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.modal {
  background: var(--bg2); border-radius: 8px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.2);
  width: min(800px, 90vw); max-height: 85vh;
  display: flex; flex-direction: column;
  animation: modalSlide 0.15s ease;
}
@keyframes modalSlide { from { transform: translateY(12px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
.modal-header {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 20px; border-bottom: 1px solid var(--border);
  background: var(--bg3); border-radius: 8px 8px 0 0;
}
.modal-header .panel-title { font-size: 0.75rem; }
.modal-close {
  font-size: 1.1rem; color: var(--text3); cursor: pointer;
  background: none; border: none; padding: 4px 8px;
  border-radius: 4px; line-height: 1;
}
.modal-close:hover { background: var(--bg4); color: var(--text); }
.modal-body {
  padding: 20px; overflow-y: auto; flex: 1;
  font-family: var(--mono); font-size: 0.8rem;
  line-height: 1.7; white-space: pre-wrap; word-break: break-word;
  color: var(--text);
}
.modal-footer {
  padding: 10px 20px; border-top: 1px solid var(--border);
  background: var(--bg3); border-radius: 0 0 8px 8px;
  display: flex; align-items: center; gap: 12px;
  font-family: var(--mono); font-size: 0.7rem; color: var(--text3);
}

/* Validation results */
.val-panel {
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow);
}
.val-header {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 14px; border-bottom: 1px solid var(--border);
  background: var(--bg3);
}
.val-badge {
  font-family: var(--mono); font-size: 0.7rem; font-weight: 700;
  padding: 2px 10px; border-radius: 12px;
}
.val-badge.pass { color: var(--green); background: var(--green-bg); }
.val-badge.fail { color: var(--red); background: rgba(204,51,68,0.08); }
.val-badge.warn { color: var(--orange); background: var(--orange-bg); }
.val-body { padding: 10px 14px; }
.val-item {
  font-family: var(--mono); font-size: 0.72rem;
  padding: 4px 0; line-height: 1.5;
  border-bottom: 1px solid var(--bg3);
  display: flex; gap: 8px; align-items: baseline;
}
.val-item:last-child { border-bottom: none; }
.val-tag {
  font-size: 0.63rem; font-weight: 700; padding: 1px 6px;
  border-radius: 3px; flex-shrink: 0;
}
.val-tag.err { color: var(--red); background: rgba(204,51,68,0.08); }
.val-tag.wrn { color: var(--orange); background: var(--orange-bg); }
.val-msg { color: var(--text2); word-break: break-word; }
.btn-validate {
  font-family: var(--mono); font-size: 0.68rem; font-weight: 600;
  padding: 3px 10px; border-radius: 4px; border: 1px solid var(--border);
  background: var(--bg2); color: var(--text2); cursor: pointer;
  transition: all 0.15s;
}
.btn-validate:hover { border-color: var(--green); color: var(--green); }
.btn-validate:disabled { opacity: 0.35; cursor: default; }
</style>
</head>
<body>
<div class="app">
  <div class="sidebar">
    <div class="sidebar-header">
      <div class="logo">&#9874; INFERENCE RUNNER</div>
      <div class="logo-sub">Ollama Model Tester</div>
    </div>
    <div class="sidebar-section">
      <label>Training File</label>
      <select id="sel-discipline" onchange="onDisciplineChange()">
        <option value="">Loading…</option>
      </select>
    </div>
    <div class="sidebar-section">
      <label>Ollama Model</label>
      <select id="sel-model"></select>
    </div>
    <div class="sidebar-section">
      <label>System Prompt</label>
      <div class="prompt-toggle">
        <button class="prompt-toggle-btn active" id="btn-mode-training" onclick="setPromptMode('training')">Training</button>
        <button class="prompt-toggle-btn" id="btn-mode-live" onclick="setPromptMode('live')">Live</button>
      </div>
    </div>
    <div class="sidebar-section" style="display:flex;gap:8px;align-items:end;">
      <div style="flex:1">
        <label>Go to Index</label>
        <input type="number" id="inp-goto" min="0" value="0" onkeydown="if(event.key==='Enter')gotoIndex()">
      </div>
      <button class="btn btn-ghost" onclick="gotoIndex()" style="margin-bottom:1px;">Go</button>
    </div>
    <div class="entry-list" id="entry-list">
      <div class="empty"><div class="empty-icon">&#128194;</div>Select a file</div>
    </div>
  </div>

  <div class="main">
    <div class="topbar">
      <div class="model-badge" id="model-badge">&mdash;</div>
      <div class="mode-badge training" id="mode-badge">TRAINING</div>
      <div class="topbar-info" id="topbar-info">No entry selected</div>
      <div class="spacer"></div>
      <button class="btn btn-ghost" id="btn-preview-sp" onclick="previewSystemPrompt()" style="font-size:0.72rem;">&#128196; View Prompt</button>
      <button class="btn btn-primary" id="btn-run" onclick="runInference()" disabled>&#9654; Run Inference</button>
      <button class="btn btn-ghost" id="btn-stop" onclick="stopInference()" style="display:none;color:var(--red);border-color:var(--red);">&#9632; Stop</button>
    </div>
    <div class="config-bar">
      <label>temp <input type="number" id="cfg-temp" value="0.7" step="0.05" min="0" max="2"></label>
      <label>top_p <input type="number" id="cfg-topp" value="0.9" step="0.05" min="0" max="1"></label>
      <label>top_k <input type="number" id="cfg-topk" value="40" step="1" min="1"></label>
      <label>max_tok <input type="number" id="cfg-max" value="2048" step="128" min="64"></label>
      <label>rep_pen <input type="number" id="cfg-rep" value="1.1" step="0.05" min="1"></label>
      <label>seed <input type="number" id="cfg-seed" value="" placeholder="random"></label>
      <label style="gap:6px;cursor:pointer;"><input type="checkbox" id="cfg-img" checked style="width:auto;cursor:pointer;"> send image</label>
    </div>
    <div class="content" id="content">
      <div class="empty"><div class="empty-icon">&#9874;</div>Select a training entry from the sidebar to begin</div>
    </div>
  </div>
</div>

<script>
let disciplines=[], entries=[], currentFile="", currentIndex=-1, currentEntry=null, running=false;
let abortController=null;
let promptMode="training"; // "training" or "live"
let lastOutput=""; // raw model output for validation

function setPromptMode(mode){
  promptMode=mode;
  console.log("[UI] promptMode set to:", promptMode);
  document.getElementById("btn-mode-training").classList.toggle("active",mode==="training");
  document.getElementById("btn-mode-live").classList.toggle("active",mode==="live");
  const badge=document.getElementById("mode-badge");
  badge.textContent=mode.toUpperCase();
  badge.className="mode-badge "+mode;
}

function stopInference(){
  if(abortController){abortController.abort();abortController=null;}
}

async function init(){
  const [dRes,mRes]=await Promise.all([
    fetch("/api/disciplines").then(r=>r.json()),
    fetch("/api/models").then(r=>r.json()),
  ]);
  disciplines=dRes;
  const sel=document.getElementById("sel-discipline");
  sel.innerHTML='<option value="">— select file —</option>';
  for(const d of disciplines){
    const o=document.createElement("option");
    o.value=d.path; o.textContent=d.name;
    o.dataset.base=d.base; o.dataset.model=d.model;
    sel.appendChild(o);
  }
  const mSel=document.getElementById("sel-model");
  mSel.innerHTML="";
  for(const m of(mRes.models||[])){
    const o=document.createElement("option");
    o.value=m; o.textContent=m; mSel.appendChild(o);
  }
}
init();

async function onDisciplineChange(){
  const sel=document.getElementById("sel-discipline");
  const opt=sel.options[sel.selectedIndex];
  currentFile=sel.value;
  if(!currentFile)return;
  const model=opt.dataset.model;
  const mSel=document.getElementById("sel-model");
  for(let i=0;i<mSel.options.length;i++){
    if(mSel.options[i].value.includes(model)||mSel.options[i].value.startsWith(model)){
      mSel.selectedIndex=i; break;
    }
  }
  const res=await fetch(`/api/entries?file=${encodeURIComponent(currentFile)}`);
  const data=await res.json();
  entries=data.entries||[];
  const list=document.getElementById("entry-list");
  list.innerHTML="";
  for(const e of entries){
    const div=document.createElement("div");
    div.className="entry-item"; div.dataset.index=e.index;
    div.innerHTML=`<span class="entry-idx">${e.index}</span><span class="entry-label">${esc(e.label)}</span>${e.has_image?'<span class="entry-img-dot"></span>':""}`;
    div.onclick=()=>selectEntry(e.index);
    list.appendChild(div);
  }
}

async function selectEntry(idx){
  currentIndex=idx;
  document.querySelectorAll(".entry-item").forEach(el=>{
    el.classList.toggle("active",parseInt(el.dataset.index)===idx);
  });
  const active=document.querySelector(".entry-item.active");
  if(active)active.scrollIntoView({block:"nearest"});
  const res=await fetch(`/api/entry?file=${encodeURIComponent(currentFile)}&index=${idx}`);
  currentEntry=await res.json();
  document.getElementById("model-badge").textContent=document.getElementById("sel-model").value;
  document.getElementById("topbar-info").textContent=`Entry #${idx} of ${entries.length}`;
  document.getElementById("btn-run").disabled=false;
  renderEntry();
}

function gotoIndex(){
  const v=parseInt(document.getElementById("inp-goto").value);
  if(!isNaN(v)&&v>=0&&v<entries.length)selectEntry(v);
}

function renderEntry(){
  if(!currentEntry)return;
  const c=document.getElementById("content");
  let imgHtml="";
  if(currentEntry.image_base64){
    imgHtml=`<div class="image-preview"><img src="data:image/png;base64,${currentEntry.image_base64}" alt="recipe grid"></div>`;
  }
  let exp=currentEntry.expected_completion||"";
  try{exp=JSON.stringify(JSON.parse(exp),null,2);}catch{}
  c.innerHTML=`${imgHtml}
    <div class="compare-grid">
      <div class="panel"><div class="panel-header"><div class="panel-dot" style="background:var(--green)"></div><div class="panel-title">Expected (Ground Truth)</div></div><div class="panel-body" id="expected-body">${esc(exp)}</div></div>
      <div class="panel"><div class="panel-header"><div class="panel-dot" style="background:var(--orange)"></div><div class="panel-title">Model Output</div><div class="spacer"></div><span id="run-indicator" style="display:none;margin-left:6px;"><span class="spinner"></span></span></div><div class="panel-body" id="model-body" style="color:var(--text3);">Click &#9654; Run Inference</div><div class="stats-bar" id="stats-bar" style="display:none;"></div></div>
    </div>
    <div id="validation-results">
      <div class="val-panel"><div class="val-header"><span class="panel-title">Validation</span></div><div class="val-body"><div class="val-item"><span class="val-msg" style="color:var(--text3);">Run inference to auto-validate model output.</span></div></div></div>
    </div>`;
}

async function previewSystemPrompt(){
  const sel=document.getElementById("sel-discipline");
  const base=sel.options[sel.selectedIndex]?.dataset.base||"";
  if(!base){alert("Select a discipline first.");return;}
  console.log("[previewPrompt] base=", base, "promptMode=", promptMode);
  // Always fetch fresh
  const res=await fetch(`/api/system_prompt?discipline=${encodeURIComponent(base)}&mode=${promptMode}`);
  const data=await res.json();
  const txt=data.prompt||"(empty)";
  const actualMode=data.mode||promptMode;
  const dotColor=actualMode==='live'?'var(--orange)':'var(--accent)';
  const charCount=txt.length;
  const wordCount=txt.split(/\s+/).filter(Boolean).length;
  // Remove existing modal if open
  const existing=document.getElementById("sp-modal");
  if(existing)existing.remove();
  // Build modal
  const overlay=document.createElement("div");
  overlay.id="sp-modal";
  overlay.className="modal-overlay";
  overlay.onclick=function(e){if(e.target===overlay)overlay.remove();};
  overlay.innerHTML=`<div class="modal">
    <div class="modal-header">
      <div class="panel-dot" style="background:${dotColor}"></div>
      <div class="panel-title">System Prompt — ${esc(base.toUpperCase())} — ${actualMode.toUpperCase()}</div>
      <div class="spacer"></div>
      <button class="modal-close" onclick="document.getElementById('sp-modal').remove()">&#10005;</button>
    </div>
    <div class="modal-body">${esc(txt)}</div>
    <div class="modal-footer">
      <span>${charCount.toLocaleString()} chars &middot; ${wordCount.toLocaleString()} words</span>
      <div class="spacer"></div>
      <span>Press Esc or click outside to close</span>
    </div>
  </div>`;
  document.body.appendChild(overlay);
  // Esc key to close
  const escHandler=function(e){if(e.key==="Escape"){overlay.remove();document.removeEventListener("keydown",escHandler);}};
  document.addEventListener("keydown",escHandler);
}

async function runInference(){
  if(running||!currentEntry)return;
  running=true;
  abortController=new AbortController();
  document.getElementById("btn-run").disabled=true;
  document.getElementById("btn-stop").style.display="";
  const model=document.getElementById("sel-model").value;
  const sel=document.getElementById("sel-discipline");
  const base=sel.options[sel.selectedIndex]?.dataset.base||"";
  console.log("[runInference] base=", base, "promptMode=", promptMode);
  const spUrl=`/api/system_prompt?discipline=${encodeURIComponent(base)}&mode=${promptMode}`;
  console.log("[runInference] fetching:", spUrl);
  const spRes=await fetch(spUrl);
  const spData=await spRes.json();
  console.log("[runInference] got prompt mode:", spData.mode, "length:", (spData.prompt||"").length);
  const systemLen=(spData.prompt||"").length;
  const body={
    model, system:spData.prompt||"", prompt:currentEntry.prompt_text||"",
    image:document.getElementById("cfg-img").checked?(currentEntry.image_base64||null):null,
    temperature:parseFloat(document.getElementById("cfg-temp").value)||0.7,
    top_p:parseFloat(document.getElementById("cfg-topp").value)||0.9,
    top_k:parseInt(document.getElementById("cfg-topk").value)||40,
    max_tokens:parseInt(document.getElementById("cfg-max").value)||2048,
    repeat_penalty:parseFloat(document.getElementById("cfg-rep").value)||1.1,
    seed:document.getElementById("cfg-seed").value?parseInt(document.getElementById("cfg-seed").value):null,
  };
  console.log("[runInference] system prompt being sent:", body.system.substring(0,100), "...("+systemLen+" chars)");
  const mb=document.getElementById("model-body");
  const ind=document.getElementById("run-indicator");
  const sb=document.getElementById("stats-bar");
  mb.textContent=""; mb.style.color="var(--text)";
  ind.style.display="inline"; sb.style.display="none";
  lastOutput="";
  const vr=document.getElementById("validation-results");
  if(vr)vr.innerHTML='<div class="val-panel"><div class="val-header"><span class="panel-title">Validation</span></div><div class="val-body"><div class="val-item"><span class="val-msg" style="color:var(--text3);">Waiting for inference…</span></div></div></div>';
  try{
    const resp=await fetch("/api/infer",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),signal:abortController.signal});
    const reader=resp.body.getReader();
    const dec=new TextDecoder();
    let buf="",full="";
    while(true){
      const{done,value}=await reader.read();
      if(done)break;
      buf+=dec.decode(value,{stream:true});
      const lines=buf.split("\n"); buf=lines.pop();
      for(const l of lines){
        if(!l.startsWith("data: "))continue;
        try{
          const evt=JSON.parse(l.slice(6));
          if(evt.error){mb.textContent+="\n\nERROR: "+evt.error;break;}
          if(evt.token){full+=evt.token;mb.textContent=full;mb.scrollTop=mb.scrollHeight;}
          if(evt.done&&evt.stats)showStats(evt.stats,promptMode,systemLen);
        }catch{}
      }
    }
    try{mb.textContent=JSON.stringify(JSON.parse(full),null,2);}catch{}
    lastOutput=full;
  }catch(err){
    if(err.name==="AbortError"){
      mb.textContent+="\n\n— stopped —";
      mb.style.color="var(--text3)";
    }else{
      mb.textContent="Connection error: "+err.message+"\nIs Ollama running?";
      mb.style.color="var(--red)";
    }
  }
  ind.style.display="none"; running=false;
  abortController=null;
  document.getElementById("btn-run").disabled=false;
  document.getElementById("btn-stop").style.display="none";
  // Auto-validate output
  if(lastOutput) validateOutput();
}

async function validateOutput(){
  if(!lastOutput)return;
  const sel=document.getElementById("sel-discipline");
  const base=sel.options[sel.selectedIndex]?.dataset.base||"";
  const vr=document.getElementById("validation-results");
  if(!vr)return;
  vr.innerHTML='<div class="val-panel"><div class="val-header"><span class="spinner"></span><span class="panel-title" style="margin-left:6px;">Validating…</span></div></div>';

  // Get expected text for comparison
  const expectedText=currentEntry?.expected_completion||"";

  try{
    const res=await fetch("/api/validate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({json_text:lastOutput,discipline:base,expected_text:expectedText})});
    const data=await res.json();
    renderValidation(data);
  }catch(err){
    vr.innerHTML=`<div class="val-panel"><div class="val-header"><span class="val-badge fail">ERROR</span><span class="panel-title">Validation Failed</span></div><div class="val-body"><div class="val-item"><span class="val-tag err">ERR</span><span class="val-msg">${esc(err.message)}</span></div></div></div>`;
  }
}

function renderValidation(data){
  const vr=document.getElementById("validation-results");
  if(!vr)return;
  const errs=data.errors||[];
  const warns=data.warnings||[];

  let badge,label;
  if(!data.json_parsed){
    badge='<span class="val-badge fail">INVALID JSON</span>';
    label="Output is not valid JSON";
  }else if(errs.length>0){
    badge='<span class="val-badge fail">'+errs.length+' ERROR'+(errs.length>1?'S':'')+'</span>';
    label="Structural issues found";
  }else if(warns.length>0){
    badge='<span class="val-badge warn">'+warns.length+' WARNING'+(warns.length>1?'S':'')+'</span>';
    label="Passed with warnings";
  }else{
    badge='<span class="val-badge pass">VALID</span>';
    label="JSON structure passed all checks";
  }

  let items="";
  for(const e of errs){
    items+=`<div class="val-item"><span class="val-tag err">ERR</span><span class="val-msg">${esc(String(e))}</span></div>`;
  }
  for(const w of warns){
    items+=`<div class="val-item"><span class="val-tag wrn">WARN</span><span class="val-msg">${esc(String(w))}</span></div>`;
  }
  if(!items&&data.json_parsed){
    items='<div class="val-item"><span class="val-msg" style="color:var(--green);">No issues detected.</span></div>';
  }

  vr.innerHTML=`<div class="val-panel"><div class="val-header">${badge}<span class="panel-title">${esc(label)}</span><div class="spacer"></div><button class="btn-validate" onclick="validateOutput()">&#8635; Re-validate</button></div><div class="val-body">${items}</div></div>`;
}

function showStats(s,mode,sysLen){
  const bar=document.getElementById("stats-bar");
  if(!s)return;
  const ts=s.total_duration?(s.total_duration/1e9).toFixed(2):"—";
  const es=s.eval_duration?(s.eval_duration/1e9):0;
  const tps=es&&s.output_tokens?(s.output_tokens/es).toFixed(1):"—";
  const modeColor=mode==='live'?'var(--orange)':'var(--accent)';
  const cached=s.prompt_tokens===0?' <span style="color:var(--red)">(cached!)</span>':'';
  bar.style.display="flex";
  bar.innerHTML=`<span style="color:${modeColor};font-weight:700;">${(mode||'?').toUpperCase()}</span><span>sys: <span class="stat-val">${(sysLen||0).toLocaleString()}</span> chars</span><span>prompt: <span class="stat-val">${s.prompt_tokens||0}</span> tok${cached}</span><span>output: <span class="stat-val">${s.output_tokens||0}</span> tok</span><span>time: <span class="stat-val">${ts}</span>s</span><span>speed: <span class="stat-val">${tps}</span> tok/s</span>`;
}

function esc(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
</script>
</body>
</html>
"""

if __name__ == "__main__":
    import webbrowser
    port = 5111
    print(f"\n  ⚒  Ollama Inference Runner")
    print(f"  ─────────────────────────")
    print(f"  JSONL dir:     {JSONL_DIR}")
    print(f"  Training prompts: {SYSTEM_PROMPT_DIR}")
    print(f"  Live prompts:     {LIVE_PROMPT_DIR}")
    print(f"  Live prompt files:")
    for disc, fname in LIVE_PROMPT_MAP.items():
        fp = os.path.join(LIVE_PROMPT_DIR, fname)
        status = "✓ found" if os.path.isfile(fp) else "✗ MISSING"
        print(f"    {disc:15s} → {fname:15s} {status}")
    print(f"  Ollama API:    {OLLAMA_API}")
    val_status = "✓ found" if os.path.isfile(VALIDATOR_PATH) else "✗ MISSING"
    print(f"  Validator:     {VALIDATOR_PATH}  {val_status}")
    print(f"  UI:            http://localhost:{port}")
    print()
    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host="127.0.0.1", port=port, debug=False)