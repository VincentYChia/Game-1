"""
Crash Handler — last-line-of-defense diagnostics for the main loop.

The packaged build runs with console=False (Game1.spec), so an unhandled
exception previously meant the window vanished with zero feedback and no
save. This module writes a timestamped crash report file the player (or a
bug report) can recover, and never raises itself.

Used by GameEngine.run()'s frame guard and by main.py's boot guard.
"""

import os
import sys
import time
import traceback
from typing import Optional


def _crash_dir() -> str:
    """Resolve the crash-report directory (next to saves; always writable)."""
    try:
        from core.paths import get_save_path
        base = str(get_save_path("crash_reports"))
    except Exception:
        base = os.path.join(os.getcwd(), "crash_reports")
    os.makedirs(base, exist_ok=True)
    return base


def write_crash_report(context: Optional[dict] = None) -> Optional[str]:
    """Write the active exception's traceback to a timestamped report file.

    Call from inside an ``except`` block. Returns the report path, or None
    if even report-writing failed (this function must never raise — it runs
    when the game is already in a failing state).
    """
    try:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(_crash_dir(), f"crash_{stamp}.txt")
        lines = [
            f"Game-1 crash report — {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Python {sys.version}",
            "",
        ]
        if context:
            lines.append("Context:")
            for key, value in context.items():
                lines.append(f"  {key}: {value}")
            lines.append("")
        lines.append(traceback.format_exc())
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"[CRASH] Report written to {path}")
        return path
    except Exception:
        # Reporting must never make a crash worse.
        try:
            traceback.print_exc()
        except Exception:
            pass
        return None
