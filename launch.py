#!/usr/bin/env python3
"""
Game-1 launcher — the single, clean way to start the Godot (3D) build.

    python launch.py              build the C# (if dotnet is present), then PLAY the
                                  game IN THIS TERMINAL, echoing each command and
                                  streaming all engine / C# / sidecar output so a
                                  crash is fully visible. Blocks until the game exits.
    python launch.py --editor     open the Godot editor on the project instead.
    python launch.py --detached   play windowless + detached (survives the launcher,
                                  tied to no terminal). No log output - use for a
                                  clean "just play" launch once things are stable.
    python launch.py --no-build   skip the dotnet build step (launch what's built).
    python launch.py --dry-run    locate Godot (+ build unless --no-build) but do not
                                  launch - prints the exact command it would run.

Godot discovery, best match first:
    1. $GODOT4 / $GODOT / $GODOT_BIN (an explicit path always wins),
    2. `godot` on PATH,
    3. common install roots (LocalAppData\\Programs\\Godot, Program Files, Downloads).
It prefers the .NET/"mono" build matching the project's Godot.NET.Sdk minor version
(pinned in Game1.Godot.csproj — currently 4.x) and the windowless (non-console) exe,
so it never grabs a mismatched Godot sitting in Downloads.

Double-click `Play Game-1.cmd` to run this without touching a terminal at all.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from shutil import which

REPO = Path(__file__).resolve().parent
GODOT_DIR = REPO / "Game-1-Godot"
CSPROJ = GODOT_DIR / "Game1.Godot.csproj"


def sdk_minor() -> str | None:
    """The Godot minor version the project targets (e.g. '4.4'), read from the SDK
    line in the .csproj so the launcher stays correct if the project is upgraded."""
    try:
        text = CSPROJ.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"Godot\.NET\.Sdk/(\d+\.\d+)", text)
    return m.group(1) if m else None


def _walk_godot_exes(root: Path, max_depth: int = 3):
    """Yield Godot executables under `root`, bounded in depth so a large Downloads
    or Program Files tree is never fully traversed."""
    if not root.exists():
        return
    root = root.resolve()
    base = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        if len(Path(dirpath).parts) - base >= max_depth:
            dirnames[:] = []
        for f in filenames:
            low = f.lower()
            if low.startswith("godot") and (low.endswith(".exe") or "." not in low):
                yield Path(dirpath) / f


def _score(exe: Path, minor: str | None) -> tuple:
    """Rank candidates so the best sorts last: right minor > mono/.NET > windowless."""
    low = exe.name.lower()
    return (
        1 if (minor and minor in low) else 0,   # matches the project's Godot 4.x
        1 if "mono" in low else 0,              # .NET build (required for the C# game)
        1 if "console" not in low else 0,       # windowless preferred (no terminal)
        low,                                    # stable, deterministic tiebreak
    )


def find_godot(minor: str | None, want_console: bool) -> Path | None:
    # 1) explicit override — trust it verbatim.
    for var in ("GODOT4", "GODOT", "GODOT_BIN"):
        val = os.environ.get(var)
        if val and Path(val).exists():
            return Path(val)

    found: list[Path] = []
    onpath = which("godot")
    if onpath:
        found.append(Path(onpath))
    roots = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Godot",
        Path(os.environ.get("ProgramFiles", "")),
        Path(os.environ.get("ProgramFiles(x86)", "")),
        Path.home() / "Downloads",
        Path.home() / "Desktop",
    ]
    for root in roots:
        if str(root) and root.exists():
            found.extend(_walk_godot_exes(root))

    pool = [p for p in dict.fromkeys(found) if p.is_file()]
    # The C# game needs a .NET/"mono" Godot; only fall back to non-mono if that's
    # genuinely all that exists (it won't run the game, but the message is clearer).
    mono = [p for p in pool if "mono" in p.name.lower()]
    pool = mono or pool
    # Console vs windowless preference (debug wants the console build for logs).
    if want_console:
        pool = [p for p in pool if "console" in p.name.lower()] or pool
    else:
        pool = [p for p in pool if "console" not in p.name.lower()] or pool
    if not pool:
        return None
    return sorted(pool, key=lambda p: _score(p, minor), reverse=True)[0]


def build_csharp(config: str) -> None:
    if which("dotnet") is None:
        print("[launch] dotnet not on PATH - skipping C# build (Godot will use the "
              "existing build, if any).")
        return
    cmd = ["dotnet", "build", str(CSPROJ), "-c", config, "-v", "minimal"]
    print(f"[launch] building C# ({config}) ...")
    print(f"[launch] run: {subprocess.list2cmdline(cmd)}")
    result = subprocess.run(cmd, cwd=str(GODOT_DIR))
    if result.returncode != 0:
        print("[launch] C# build FAILED - fix the errors above, then retry.",
              file=sys.stderr)
        sys.exit(result.returncode)


def launch(godot: Path, *, editor: bool, detached: bool) -> int:
    args = [str(godot), "--path", str(GODOT_DIR)]
    if editor:
        args.append("-e")
    print(f"[launch] run: {subprocess.list2cmdline(args)}")

    if not detached:
        # Foreground (default): inherit this terminal's stdio so every engine / C# /
        # Python-sidecar line — including a crash traceback — is printed right here.
        # Blocks until the game window closes.
        return subprocess.run(args, cwd=str(GODOT_DIR)).returncode

    # Detached + windowless (opt-in): the game keeps running after this launcher exits
    # and is tied to no terminal. (The game reaps its Python sidecar via a Windows Job
    # Object, so nothing is left spinning when you close the window.)
    kwargs: dict = dict(
        cwd=str(GODOT_DIR),
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, **kwargs)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Launch the Game-1 Godot (3D) build.")
    ap.add_argument("--editor", action="store_true",
                    help="open the Godot editor instead of playing the game")
    ap.add_argument("--detached", action="store_true",
                    help="play windowless + detached instead of in this terminal")
    ap.add_argument("--no-build", action="store_true",
                    help="skip the dotnet C# build step")
    ap.add_argument("--config", default="Debug",
                    help="dotnet build configuration (default: Debug)")
    ap.add_argument("--dry-run", action="store_true",
                    help="locate Godot and build, but don't launch")
    args = ap.parse_args(argv)

    if not CSPROJ.exists():
        print(f"[launch] can't find {CSPROJ}\n         run this from the Game-1 repo "
              "root (it lives next to Game-1-Godot/).", file=sys.stderr)
        return 2

    # Foreground (default) uses the *console* Godot build so logs/crashes print into
    # the terminal; a detached "just play" launch uses the windowless build.
    minor = sdk_minor()
    godot = find_godot(minor, want_console=not args.detached)
    if godot is None:
        print("[launch] No .NET/mono Godot found.\n"
              "         Install the Godot 4 'mono' (.NET) build, or set GODOT4 to "
              "its full path, e.g.\n"
              '         setx GODOT4 "C:\\path\\to\\Godot_v4.4-stable_mono_win64.exe"',
              file=sys.stderr)
        return 3
    print(f"[launch] Godot:   {godot}")
    print(f"[launch] project: {GODOT_DIR}")

    if not args.no_build:
        build_csharp(args.config)

    if args.dry_run:
        cmd = [str(godot), "--path", str(GODOT_DIR)] + (["-e"] if args.editor else [])
        print(f"[launch] dry run - would launch: {' '.join(cmd)}")
        return 0

    mode = "editor" if args.editor else ("detached play" if args.detached else "play")
    print(f"[launch] starting Game-1 ({mode}) ...")
    return launch(godot, editor=args.editor, detached=args.detached)


if __name__ == "__main__":
    raise SystemExit(main())
