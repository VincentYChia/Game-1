"""Prompt Studio entry point.

Run from the project root::

    cd Game-1-modular
    python tools/prompt_studio_main.py

The actual application lives in :mod:`tools.prompt_studio.app`. This
file exists so the studio is invokable as a single command without
having to write ``python -m tools.prompt_studio.app``.

(The legacy ``tools/prompt_editor.py`` is kept in place for designers
who only need WMS Layer 2 fragment editing — the new studio supersedes
it but does not delete it.)
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from tools.prompt_studio.app import main as run_app
    run_app()


if __name__ == "__main__":
    main()
