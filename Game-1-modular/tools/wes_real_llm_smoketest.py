"""Real-LLM smoke harness for the WES pipeline.

Exercises the BackendManager against a single task with both env
toggles set, surfacing whether the configured Ollama / Claude
deployments are actually reachable. Designed to be run by an operator
before a playtest session — exit code 0 means "good to go", non-zero
means "fix your env first."

Usage::

    cd Game-1-modular
    python tools/wes_real_llm_smoketest.py
    python tools/wes_real_llm_smoketest.py --task wes_tool_chunks
    python tools/wes_real_llm_smoketest.py --backend ollama
    python tools/wes_real_llm_smoketest.py --no-require-real

The script:

1. Sets ``WES_DISABLE_FIXTURES=1`` (skips the canonical fixture
   shortcut so MockBackend doesn't intercept).
2. Sets ``WES_REQUIRE_REAL_LLM=1`` by default (strips MockBackend from
   the fallback chain so an unreachable real backend produces a
   visible failure rather than a silent template response).
3. Builds a small test prompt and routes it through
   :class:`BackendManager` for the chosen task code.
4. Prints a structured status report (per-backend availability,
   resolved chain, response preview) and exits with a clean code.

This is a CLI harness, not a unit test — it deliberately makes real
network calls when backends are reachable. CI should run it as a
smoke check on dev branches that touch the LLM stack, marked
skip-if-no-server.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))


def _print_block(title: str, lines: list) -> None:
    print()
    print(f"-- {title} " + "-" * max(2, 60 - len(title)))
    for line in lines:
        print(f"  {line}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task", default="wes_tool_chunks",
        help="Task code to test (default: wes_tool_chunks).",
    )
    parser.add_argument(
        "--backend", default=None,
        help="Force a specific backend by name (skips routing).",
    )
    parser.add_argument(
        "--no-disable-fixtures", action="store_true",
        help="Don't set WES_DISABLE_FIXTURES — useful for verifying the "
             "fixture path itself works without the gate.",
    )
    parser.add_argument(
        "--no-require-real", action="store_true",
        help="Don't set WES_REQUIRE_REAL_LLM — let MockBackend templates "
             "act as final fallback if real backends fail.",
    )
    parser.add_argument(
        "--system-prompt", default="You are a test prompt.",
    )
    parser.add_argument(
        "--user-prompt", default="Echo a single short sentence as response.",
    )
    args = parser.parse_args()

    # Configure env BEFORE importing BackendManager so the toggles
    # apply at module load time.
    if not args.no_disable_fixtures:
        os.environ["WES_DISABLE_FIXTURES"] = "1"
    if not args.no_require_real:
        os.environ["WES_REQUIRE_REAL_LLM"] = "1"

    from world_system.living_world.backends.backend_manager import (
        BackendManager,
        _fixtures_disabled,
        _require_real_llm,
    )

    _print_block("Environment", [
        f"WES_DISABLE_FIXTURES = {os.environ.get('WES_DISABLE_FIXTURES', '(unset)')!r}  "
        f"-> fixtures_disabled() = {_fixtures_disabled()}",
        f"WES_REQUIRE_REAL_LLM  = {os.environ.get('WES_REQUIRE_REAL_LLM', '(unset)')!r}  "
        f"-> require_real_llm() = {_require_real_llm()}",
        f"ANTHROPIC_API_KEY set: {bool(os.environ.get('ANTHROPIC_API_KEY'))}",
    ])

    mgr = BackendManager.get_instance()
    if not mgr._initialized:
        mgr.initialize()

    # Backend availability snapshot.
    avail_lines = []
    for name, backend in (mgr._backends or {}).items():
        try:
            ok = backend.is_available()
        except Exception as e:
            ok = False
            avail_lines.append(f"{name}: is_available raised {type(e).__name__}: {e}")
            continue
        info = backend.get_info() if hasattr(backend, "get_info") else {}
        model = info.get("model", "?")
        avail_lines.append(
            f"{name}: {'AVAILABLE' if ok else 'unavailable'}  "
            f"(model={model})"
        )
    _print_block("Backends", avail_lines or ["(no backends configured)"])

    # Resolved chain for this task.
    primary = mgr._task_routing.get(args.task, mgr._fallback_chain[0] if mgr._fallback_chain else "?")
    chain = [primary]
    for name in mgr._fallback_chain:
        if name not in chain:
            chain.append(name)
    if _require_real_llm() and not args.backend:
        chain_after = [n for n in chain if n != "mock"]
    else:
        chain_after = list(chain)
    _print_block("Routing", [
        f"task code:        {args.task}",
        f"primary:          {primary}",
        f"fallback chain:   {' ->'.join(chain)}",
        f"after gate strip: {' ->'.join(chain_after) or '(empty — guaranteed failure)'}",
        f"backend_override: {args.backend or '(none)'}",
    ])

    # Issue the call.
    print()
    print(f"-- Generating ({args.task}) " + "-" * 30)
    text, err = mgr.generate(
        task=args.task,
        system_prompt=args.system_prompt,
        user_prompt=args.user_prompt,
        backend_override=args.backend,
    )

    if err:
        print(f"  [X] ERROR:{err}")
        print()
        if "All backends failed" in err:
            print("  Likely cause: no real LLM backend is reachable.")
            print("  Mitigations:")
            print("    1. Start an Ollama server (default: http://localhost:11434).")
            print("    2. Or set ANTHROPIC_API_KEY for Claude.")
            print("    3. Or re-run with --no-require-real to allow MockBackend templates.")
        return 1

    preview = text[:400] + ("..." if len(text) > 400 else "")
    print(f"  [OK]Response ({len(text)} chars):")
    print()
    for line in preview.splitlines() or [""]:
        print(f"    {line}")
    print()
    print("  [OK]Real-LLM smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
