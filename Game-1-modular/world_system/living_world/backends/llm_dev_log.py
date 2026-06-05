"""LLM dev log — comprehensive write-only sink for every BackendManager call.

User direction (2026-06-05): Claude-only playtest posture. They want every
LLM round-trip captured so behaviour can be audited without terminal
spam. This module writes structured JSONL records to
``llm_debug_logs/wes_<session>.jsonl`` (one record per call, append-only).

Records carry:

- timestamp, session_id, sequence number
- task, backend used, model name
- system_prompt + user_prompt (full text)
- response text + error string
- elapsed seconds, prompt char count, response char count
- any extra metadata the caller passes via ``log_extra``

Designer-facing helper :func:`tail_recent` reads the tail of the current
session log for the observability overlay / Prompt Studio Simulator.

The log writer is best-effort — disk failure must never break a
playtest. Every public call wraps in try/except.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


_SESSION_ID = uuid.uuid4().hex[:12]
_SESSION_SEQ = 0
_SESSION_LOCK = threading.Lock()
_DISABLED = False


def _log_dir() -> Path:
    """Return the log directory, creating it on first call. The
    location is ``<project_root>/llm_debug_logs/`` — same parent as the
    legacy crafting LLM log so playtest log triage lives in one place."""
    here = Path(__file__).resolve().parent
    # backends/ → living_world/ → world_system/ → Game-1-modular/
    project_root = here.parent.parent.parent
    log_dir = project_root / "llm_debug_logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return log_dir


def _log_path() -> Path:
    return _log_dir() / f"wes_{_SESSION_ID}.jsonl"


@dataclass
class LLMCallRecord:
    """One row of the dev log. JSON-serialisable."""
    seq: int
    ts: float
    session_id: str
    task: str
    backend: str
    model: str
    system_prompt: str
    user_prompt: str
    response: str
    error: Optional[str]
    elapsed_s: float
    prompt_chars: int
    response_chars: int
    extra: Dict[str, Any] = field(default_factory=dict)


def record_call(
    *,
    task: str,
    backend: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response: str,
    error: Optional[str],
    elapsed_s: float,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Append one record to the dev log. Best-effort; swallows IO errors."""
    if _DISABLED:
        return
    global _SESSION_SEQ
    try:
        with _SESSION_LOCK:
            _SESSION_SEQ += 1
            seq = _SESSION_SEQ
        rec = LLMCallRecord(
            seq=seq,
            ts=time.time(),
            session_id=_SESSION_ID,
            task=task,
            backend=backend,
            model=model,
            system_prompt=system_prompt or "",
            user_prompt=user_prompt or "",
            response=response or "",
            error=error,
            elapsed_s=float(elapsed_s),
            prompt_chars=len((system_prompt or "")) + len((user_prompt or "")),
            response_chars=len(response or ""),
            extra=extra or {},
        )
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
    except Exception:
        # Never break a playtest because the disk is full.
        return


def tail_recent(n: int = 15) -> List[Dict[str, Any]]:
    """Return the last ``n`` records as parsed dicts. Used by the F12
    observability overlay and Prompt Studio Simulator."""
    path = _log_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-int(n):]
        out: List[Dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out
    except Exception:
        return []


def session_id() -> str:
    """Stable session UUID assigned at module import."""
    return _SESSION_ID


def log_path() -> Path:
    return _log_path()


def disable() -> None:
    """Test helper — silence the writer."""
    global _DISABLED
    _DISABLED = True


def enable() -> None:
    """Test helper — re-enable the writer."""
    global _DISABLED
    _DISABLED = False
