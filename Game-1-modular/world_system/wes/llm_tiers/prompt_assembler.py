"""PromptAssembler — builds WES prompts from JSON fragment files (§6.6).

Follows the existing ``prompt_fragments_l*.json`` shape used by WMS:

    {
      "_meta": {...},
      "_core": { "system": "...", "user_template": "..." },
      "_output": { "schema": "...", "example": "..." }
    }

``${placeholder}`` tokens inside ``_core.system`` and ``_core.user_template``
are substituted with caller-supplied variables. Unresolved placeholders
are left as-is so misses show up visibly in logs rather than silently
vanishing.

The assembler is also the single place where the shared **game awareness**
(tier multipliers, known biomes taxonomy, address tag prefixes) and
**task awareness** (output schema, constraints) blocks are injected. Per
§5.2 these blocks ride every WES tier's system prompt.

All fragment files are placeholders per PLACEHOLDER_LEDGER §6; the
assembler doesn't care about their specific text — it just loads + fills.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional


# ── Shared awareness blocks (§5.2) ────────────────────────────────────
# These are concise, static facts every WES tier needs. Designer can
# later extract to their own JSON config — for P6-P9 scaffolding they
# live in code.

_GAME_AWARENESS_BLOCK = (
    "\n\n[GAME AWARENESS]\n"
    "Tier multipliers (immutable): T1=1.0x, T2=2.0x, T3=4.0x, T4=8.0x.\n"
    "Known tools: hostiles, materials, nodes, skills, titles. "
    "quests is deferred; do not plan quests.\n"
    "Address tag prefixes: world:, nation:, region:, province:, "
    "district:, locality:.\n"
    "Tag vocabulary is sacred — do not invent new tags.\n"
)

_TASK_AWARENESS_DEFAULT = (
    "\n\n[TASK AWARENESS]\n"
    "Output must be strictly valid JSON (or XML where specified). "
    "Do not emit prose preamble or markdown fences.\n"
)


_PLACEHOLDER_RE = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class PromptAssembler:
    """Loads a prompt-fragments JSON file and builds system + user prompts.

    One assembler instance per prompt file. Cached in memory after first
    load; call :meth:`reload` to refresh during dev.
    """

    def __init__(self, fragments_path: str):
        self.fragments_path = fragments_path
        self._fragments: Optional[Dict[str, Any]] = None

    # ── loading ──────────────────────────────────────────────────────

    def _load(self) -> Dict[str, Any]:
        if self._fragments is not None:
            return self._fragments
        if not os.path.exists(self.fragments_path):
            # Missing fragment file is recoverable — an empty dict still
            # lets assembly proceed with just awareness blocks + user data.
            # TODO: designer may prefer a hard failure here.
            self._fragments = {}
            return self._fragments
        try:
            with open(self.fragments_path, "r", encoding="utf-8") as f:
                self._fragments = json.load(f)
        except Exception:
            self._fragments = {}
        return self._fragments

    def reload(self) -> None:
        """Discard the in-memory copy; next call to :meth:`build` reloads."""
        self._fragments = None

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def substitute(text: str, variables: Dict[str, Any]) -> str:
        """Replace ``${var}`` tokens in ``text`` from ``variables``.

        Unknown variables are left verbatim (visible in output) so issues
        surface in logs rather than silently disappearing.
        """
        if not text:
            return ""

        def _repl(match: "re.Match[str]") -> str:
            key = match.group(1)
            if key in variables:
                val = variables[key]
                if isinstance(val, (dict, list)):
                    return json.dumps(val, ensure_ascii=False)
                return str(val)
            return match.group(0)

        return _PLACEHOLDER_RE.sub(_repl, text)

    # ── public API ───────────────────────────────────────────────────

    def build(
        self,
        variables: Optional[Dict[str, Any]] = None,
        *,
        include_game_awareness: bool = True,
        include_task_awareness: bool = True,
        firing_tier: Optional[int] = None,
        extra_system_suffix: str = "",
    ) -> Dict[str, str]:
        """Return ``{"system": ..., "user": ..., "output_example": ...}``.

        - ``variables`` are substituted into both ``_core.system`` and
          ``_core.user_template``.
        - ``firing_tier``, when provided and the fragments expose a
          ``scope_by_firing_tier`` map under ``_core``, injects that
          tier's scope rule into the system prompt.
        - ``output_example`` is populated from ``_output.example`` when
          present; useful for retry-with-stricter-prompt flows.
        """
        vars_ = dict(variables or {})
        frags = self._load()
        core = frags.get("_core", {})
        out = frags.get("_output", {})

        system_tmpl = core.get("system", "")
        user_tmpl = core.get("user_template", "")

        # firing_tier-specific scope discipline (PLACEHOLDER_LEDGER §7)
        scope_block = ""
        scope_map = core.get("scope_by_firing_tier")
        if firing_tier is not None and isinstance(scope_map, dict):
            scope_block = "\n\n[SCOPE DISCIPLINE]\n" + str(
                scope_map.get(str(firing_tier)) or scope_map.get(firing_tier) or ""
            )

        system = self.substitute(system_tmpl, vars_)
        if include_game_awareness:
            system += _GAME_AWARENESS_BLOCK
        if include_task_awareness:
            system += _TASK_AWARENESS_DEFAULT
        system += scope_block
        if extra_system_suffix:
            system += "\n\n" + extra_system_suffix

        user = self.substitute(user_tmpl, vars_)

        return {
            "system": system,
            "user": user,
            "output_example": str(out.get("example", "")),
        }


__all__ = ["PromptAssembler"]
