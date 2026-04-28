"""Prompt Studio — comprehensive UI for designing & validating every
LLM prompt the game uses.

Top-level entry: ``tools/prompt_studio.py`` (alongside this package).

Public submodules:

- :mod:`tools.prompt_studio.registry`   — declarative metadata for every
  LLM task (32 of them, across WMS / WNS / WES / NPC tiers).
- :mod:`tools.prompt_studio.sample_inputs` — builds realistic input vars
  for each task using the live game databases.
- :mod:`tools.prompt_studio.app`        — Tkinter app with six panels.
"""

from tools.prompt_studio.registry import (
    LLMSystem,
    SystemTier,
    AssemblerStyle,
    OutputFormat,
    SystemRegistry,
)

__all__ = [
    "LLMSystem",
    "SystemTier",
    "AssemblerStyle",
    "OutputFormat",
    "SystemRegistry",
]
