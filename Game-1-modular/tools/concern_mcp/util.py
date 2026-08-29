"""Shared filesystem/util helpers for the concern-registry extractors."""

from __future__ import annotations

import hashlib
import os
from typing import Iterable, Iterator, Set

# Dirs never worth indexing (build bundles, caches, runtime state, vendored trees).
SKIP_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv", "env", "ENV",
    "dist", "build", "obj", "bin", ".godot", ".idea", ".vscode",
    "saves", "llm_debug_logs", ".pytest_cache", "archive",
}


def rel(path: str, root: str) -> str:
    """Repo-root-relative, forward-slashed path (openable/clickable)."""
    return os.path.relpath(path, root).replace("\\", "/")


def file_hash(path: str) -> str:
    h = hashlib.sha1()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def read_text(path: str) -> str:
    """Read a source/JSON file tolerating the common encodings in this repo."""
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, OSError):
            continue
    return ""


def iter_files(scan_root: str, exts: Set[str],
               extra_skip: Iterable[str] = ()) -> Iterator[str]:
    skip = SKIP_DIRS | set(extra_skip)
    exts = {e.lower() for e in exts}
    for dirpath, dirnames, filenames in os.walk(scan_root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in exts:
                yield os.path.join(dirpath, fn)
