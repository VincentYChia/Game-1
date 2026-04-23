"""LLM Fixture Registry core (v4 P0 — CC4).

Defines the ``LLMFixture`` dataclass and the ``LLMFixtureRegistry`` singleton.
Built-in fixtures live in ``builtin.py`` and are registered there at module
import; external code can also call ``register()`` to add more.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Dict, List, Optional


# Known LLM tier buckets — used for filtering and test grouping.
TIER_WMS = "wms"           # World Memory System consolidators / summarizers
TIER_WNS = "wns"           # World Narrative System weavers
TIER_WES = "wes"           # World Executor System (planner / hub / tool / supervisor)
TIER_NPC = "npc"           # NPC dialogue (speech-bank generation)
TIER_MISC = "misc"


@dataclass(frozen=True)
class LLMFixture:
    """Canonical mock I/O for one LLM role.

    Fixtures are immutable once registered. Tests use them as golden
    examples; ``MockBackend`` uses ``canonical_response`` as a deterministic
    stand-in when real backends are unavailable.

    Attributes:
        code: Stable identifier matching BackendManager task names
              (e.g. ``wns_layer2``, ``wes_hub_materials``). Canonical
              casing: lowercase snake_case.
        tier: One of ``TIER_WMS``, ``TIER_WNS``, ``TIER_WES``, ``TIER_NPC``,
              ``TIER_MISC``. Used for filtering.
        description: Human-readable description of what this LLM does.
        canonical_system_prompt: Example system prompt this LLM receives.
                                 Should be schema-faithful, not trivial.
        canonical_user_prompt: Example user prompt.
        canonical_response: Representative valid response. For structured
                            outputs (JSON), this must be schema-compliant.
        notes: Optional design notes (e.g. "quests deferred; stub only").
    """

    code: str
    tier: str
    description: str
    canonical_system_prompt: str
    canonical_user_prompt: str
    canonical_response: str
    notes: str = ""


class LLMFixtureRegistry:
    """Singleton registry of all LLM fixtures.

    Use ``get_fixture_registry()`` to access the global instance. Fixtures
    are registered by module-import side-effect (see ``builtin.py``).
    Duplicate codes raise ``ValueError`` — codes must be unique.
    """

    _instance: ClassVar[Optional["LLMFixtureRegistry"]] = None

    def __init__(self) -> None:
        self._fixtures: Dict[str, LLMFixture] = {}

    @classmethod
    def get_instance(cls) -> "LLMFixtureRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper — discard the singleton and its registrations."""
        cls._instance = None

    # ── mutation ─────────────────────────────────────────────────────

    def register(self, fixture: LLMFixture) -> None:
        """Register a fixture. Raises ValueError on duplicate code."""
        if fixture.code in self._fixtures:
            raise ValueError(
                f"LLMFixture code '{fixture.code}' already registered"
            )
        self._fixtures[fixture.code] = fixture

    # ── lookup ───────────────────────────────────────────────────────

    def get(self, code: str) -> Optional[LLMFixture]:
        """Return the fixture for ``code`` or None if not registered."""
        return self._fixtures.get(code)

    def require(self, code: str) -> LLMFixture:
        """Return the fixture for ``code`` or raise KeyError."""
        f = self._fixtures.get(code)
        if f is None:
            raise KeyError(f"No LLMFixture registered for code '{code}'")
        return f

    def has(self, code: str) -> bool:
        return code in self._fixtures

    def codes(self) -> List[str]:
        """Return all registered fixture codes, sorted."""
        return sorted(self._fixtures.keys())

    def by_tier(self, tier: str) -> List[LLMFixture]:
        """Return fixtures in a given tier, sorted by code."""
        return sorted(
            (f for f in self._fixtures.values() if f.tier == tier),
            key=lambda f: f.code,
        )

    @property
    def stats(self) -> Dict[str, int]:
        """Counts per tier — useful for test assertions."""
        counts: Dict[str, int] = {}
        for f in self._fixtures.values():
            counts[f.tier] = counts.get(f.tier, 0) + 1
        counts["_total"] = len(self._fixtures)
        return counts


def get_fixture_registry() -> LLMFixtureRegistry:
    """Module-level accessor following project singleton pattern."""
    return LLMFixtureRegistry.get_instance()
