"""LLM Fixture Registry (v4 P0 — CC4).

Every LLM role in the Living World gets:

1. A **fixture code** — a short stable identifier (e.g. ``wns_layer2``,
   ``wes_hub_materials``) that names the role across config and tests.
2. A **canonical mock I/O pair** — a representative system+user prompt
   shape and a representative valid response. Used by tests and by
   ``MockBackend`` when real backends are unavailable.

The registry is the single source of truth for "every LLM in the system,
one entry per role, with data to exercise it end-to-end."

Call ``get_fixture_registry()`` to access the singleton. Fixtures are
registered at module import — see ``builtin.py`` for the registered set.

Usage:

    reg = get_fixture_registry()
    fixture = reg.get("wns_layer2")
    response = fixture.canonical_response  # used by MockBackend

    # enumerate all fixtures (tests)
    for code in reg.codes():
        f = reg.get(code)
        ...
"""

from __future__ import annotations

from .registry import (
    LLMFixture,
    LLMFixtureRegistry,
    get_fixture_registry,
)

# Register built-in fixtures at import time.
from . import builtin  # noqa: F401 — side-effect import

__all__ = [
    "LLMFixture",
    "LLMFixtureRegistry",
    "get_fixture_registry",
]
