"""Tests for the LLM Fixture Registry (v4 P0 — CC4).

Verifies:
1. Registry is a singleton.
2. Built-in fixtures are registered at import time.
3. Every major LLM role has a fixture code.
4. Fixtures are immutable (frozen dataclass).
5. Duplicate registration raises ValueError.
6. by_tier filtering and stats work.
7. Canonical responses are valid JSON where the role produces JSON.
"""

from __future__ import annotations

import json
import os
import sys
import unittest

_this_dir = os.path.dirname(os.path.abspath(__file__))
_game_dir = os.path.dirname(os.path.dirname(os.path.dirname(_this_dir)))
if _game_dir not in sys.path:
    sys.path.insert(0, _game_dir)

from world_system.living_world.infra.llm_fixtures import (  # noqa: E402
    LLMFixture,
    LLMFixtureRegistry,
    get_fixture_registry,
)
from world_system.living_world.infra.llm_fixtures.registry import (  # noqa: E402
    TIER_NPC,
    TIER_WES,
    TIER_WMS,
    TIER_WNS,
)


# Roles we expect the built-in set to cover. If a new role is added, extend
# this list.
EXPECTED_CODES = [
    # WMS (shipped parity)
    "wms_layer3", "wms_layer4", "wms_layer5", "wms_layer6", "wms_layer7",
    # WNS (v4 new)
    "wns_layer2", "wns_layer3", "wns_layer4",
    "wns_layer5", "wns_layer6", "wns_layer7",
    # WES (v4 new)
    "wes_execution_planner",
    "wes_hub_hostiles", "wes_hub_materials", "wes_hub_nodes",
    "wes_hub_skills", "wes_hub_titles",
    "wes_tool_hostiles", "wes_tool_materials", "wes_tool_nodes",
    "wes_tool_skills", "wes_tool_titles",
    "wes_supervisor",
    # NPC dialogue (pre-generated speech-bank)
    "npc_dialogue_speechbank",
]

# Roles whose canonical response must parse as JSON (the plain-XML WES hub
# responses are the exception).
JSON_RESPONSE_CODES = {
    c for c in EXPECTED_CODES
    if not c.startswith("wes_hub_")
}


class TestLLMFixtureRegistry(unittest.TestCase):

    def setUp(self) -> None:
        # Do NOT reset the singleton — the built-in fixtures are registered
        # at module import time, and resetting would lose them.
        self.reg = get_fixture_registry()

    def test_singleton(self) -> None:
        a = LLMFixtureRegistry.get_instance()
        b = LLMFixtureRegistry.get_instance()
        self.assertIs(a, b)
        self.assertIs(a, self.reg)

    def test_every_expected_role_registered(self) -> None:
        for code in EXPECTED_CODES:
            with self.subTest(code=code):
                self.assertTrue(
                    self.reg.has(code),
                    f"Missing fixture for LLM role '{code}'",
                )
                fixture = self.reg.get(code)
                self.assertIsNotNone(fixture)
                self.assertEqual(fixture.code, code)

    def test_canonical_responses_parse_as_json_where_expected(self) -> None:
        for code in JSON_RESPONSE_CODES:
            with self.subTest(code=code):
                fixture = self.reg.require(code)
                try:
                    json.loads(fixture.canonical_response)
                except json.JSONDecodeError as e:
                    self.fail(
                        f"Fixture '{code}' canonical_response is not valid JSON: {e}"
                    )

    def test_hub_responses_look_like_xml_batches(self) -> None:
        for code in self.reg.codes():
            if not code.startswith("wes_hub_"):
                continue
            with self.subTest(code=code):
                resp = self.reg.require(code).canonical_response
                self.assertIn(
                    "<specs", resp,
                    f"Hub fixture '{code}' should emit <specs> XML batch "
                    f"(CC9 non-adaptive dispatcher)",
                )
                self.assertIn("</specs>", resp)

    def test_immutability(self) -> None:
        # LLMFixture is a frozen dataclass — trying to mutate fails.
        fixture = self.reg.require("wns_layer2")
        with self.assertRaises(Exception):
            fixture.code = "mutated"  # type: ignore

    def test_duplicate_registration_raises(self) -> None:
        dup = LLMFixture(
            code="wns_layer2",
            tier=TIER_WNS,
            description="duplicate",
            canonical_system_prompt="",
            canonical_user_prompt="",
            canonical_response="{}",
        )
        with self.assertRaises(ValueError):
            self.reg.register(dup)

    def test_by_tier_filtering(self) -> None:
        wns = self.reg.by_tier(TIER_WNS)
        wes = self.reg.by_tier(TIER_WES)
        wms = self.reg.by_tier(TIER_WMS)
        npc = self.reg.by_tier(TIER_NPC)

        self.assertGreaterEqual(len(wns), 6)  # NL2-NL7
        self.assertGreaterEqual(len(wes), 12)  # planner + 5 hubs + 5 tools + supervisor
        self.assertGreaterEqual(len(wms), 5)
        self.assertGreaterEqual(len(npc), 1)

    def test_stats_totals(self) -> None:
        stats = self.reg.stats
        self.assertIn("_total", stats)
        self.assertGreaterEqual(stats["_total"], len(EXPECTED_CODES))
        self.assertIn(TIER_WNS, stats)
        self.assertIn(TIER_WES, stats)

    def test_unknown_code_returns_none(self) -> None:
        self.assertIsNone(self.reg.get("nonexistent_role_code"))

    def test_require_raises_on_unknown(self) -> None:
        with self.assertRaises(KeyError):
            self.reg.require("nonexistent_role_code")


if __name__ == "__main__":
    unittest.main()
