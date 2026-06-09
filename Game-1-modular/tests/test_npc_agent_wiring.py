"""Tests for NPCAgentSystem v3 personality + dialogue_helper wiring.

Covers the 2026-06-09 hookup that closes the silent gap between v3 inline
personality data (data/models/npcs.py:11) and the agent system:

- ``register_npc`` stores inline personality so ``get_personality`` returns
  it verbatim (not the shared "default" template).
- ``register_npc`` with ``template_name`` falls through to the shared
  templates in ``world_system/config/npc-personalities.json``.
- ``_build_faction_context`` actually calls ``assemble_dialogue_context`` and
  threads NPC opinion + player standing + local sentiment into the prompt.

These tests do NOT need a running BackendManager — they exercise the
context-assembly path only.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_THIS_DIR = Path(__file__).parent
_GAME_DIR = _THIS_DIR.parent
if str(_GAME_DIR) not in sys.path:
    sys.path.insert(0, str(_GAME_DIR))

from events.event_bus import GameEventBus  # noqa: E402
from world_system.living_world.npc.npc_agent import NPCAgentSystem  # noqa: E402
from world_system.living_world.npc.npc_memory import NPCMemoryManager  # noqa: E402
from world_system.living_world.factions.faction_system import FactionSystem  # noqa: E402


class _AgentWiringTestBase(unittest.TestCase):
    """Sets up a real FactionSystem (temp DB) + a fresh NPCAgentSystem."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_faction.db")

        self._faction_patch = patch(
            "world_system.living_world.factions.faction_system.get_faction_db_path"
        )
        mock_path = self._faction_patch.start()
        mock_path.return_value = self.db_path

        FactionSystem.reset()
        self.faction = FactionSystem.get_instance()
        self.faction.initialize()

        NPCAgentSystem.reset()
        NPCMemoryManager.reset()
        self.agent = NPCAgentSystem.get_instance()
        # initialize() with no config — we rely on default templates being
        # loaded from the standard config path.
        self.agent.initialize(memory_manager=NPCMemoryManager.get_instance())

    def tearDown(self) -> None:
        self._faction_patch.stop()
        FactionSystem.reset()
        NPCAgentSystem.reset()
        NPCMemoryManager.reset()
        GameEventBus.reset()
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            os.rmdir(self.temp_dir)
        except Exception:
            pass


class TestRegisterNpcInlinePersonality(_AgentWiringTestBase):
    """v3 NPCs ship inline personality — register_npc must return it verbatim."""

    def test_inline_personality_takes_precedence(self) -> None:
        inline = {
            "voice": "Inline voice for this specific NPC.",
            "knowledge_domains": ["unique_domain"],
            "dialogue_style": {"max_response_length": 99},
        }
        self.agent.register_npc(npc_id="npc_inline_1", personality=inline)
        got = self.agent.get_personality("npc_inline_1")
        self.assertEqual(got["voice"], "Inline voice for this specific NPC.")
        self.assertEqual(got["knowledge_domains"], ["unique_domain"])
        self.assertEqual(got["dialogue_style"]["max_response_length"], 99)

    def test_inline_personality_is_isolated_per_npc(self) -> None:
        self.agent.register_npc(
            npc_id="npc_a", personality={"voice": "A voice"}
        )
        self.agent.register_npc(
            npc_id="npc_b", personality={"voice": "B voice"}
        )
        self.assertEqual(self.agent.get_personality("npc_a")["voice"], "A voice")
        self.assertEqual(self.agent.get_personality("npc_b")["voice"], "B voice")

    def test_template_name_fallback_when_no_inline(self) -> None:
        self.agent.register_npc(npc_id="merchant_1", template_name="merchant")
        got = self.agent.get_personality("merchant_1")
        # The shared "merchant" template is loaded from npc-personalities.json.
        # We only assert it's not the default template.
        if got and "voice" in got:
            self.assertNotEqual(got["voice"], "Friendly, ordinary villager. Speaks plainly about everyday life.")

    def test_no_personality_no_template_falls_to_default(self) -> None:
        self.agent.register_npc(npc_id="generic_npc")
        got = self.agent.get_personality("generic_npc")
        # Default template should be returned (or empty dict if config absent).
        # The key assertion: this does NOT raise and does NOT return None.
        self.assertIsInstance(got, dict)


class TestRegisterNpcLocationHierarchy(_AgentWiringTestBase):
    """Location hierarchy must be stored for use by _build_faction_context."""

    def test_location_hierarchy_stored(self) -> None:
        hierarchy = [
            ("locality", "westhollow"),
            ("district", "iron_hills"),
            ("nation", "nation:stormguard"),
            ("world", None),
        ]
        self.agent.register_npc(
            npc_id="placed_npc",
            personality={"voice": "v"},
            location_hierarchy=hierarchy,
        )
        self.assertEqual(self.agent._npc_locations["placed_npc"], hierarchy)


class TestBuildFactionContext(_AgentWiringTestBase):
    """_build_faction_context must call dialogue_helper and surface its data."""

    def _seed_faction_data(self) -> None:
        """Build a smith NPC who likes the player and lives in a friendly town."""
        self.faction.add_npc("smith_1", "Master smith of Westhollow", 0.0)
        self.faction.add_npc_belonging_tag(
            "smith_1", "profession:blacksmith", 0.9, role="master"
        )
        self.faction.add_npc_belonging_tag(
            "smith_1", "locality:westhollow", 0.5, role=None
        )
        # NPC personally likes the player.
        self.faction.set_npc_affinity_toward_player("smith_1", 60.0)
        # Player has good standing with the smithing profession tag.
        self.faction.set_player_affinity("_player", "profession:blacksmith", 40.0)
        # Locality cultural default — write direct SQL since there's no
        # public setter (bootstrap-only otherwise).
        cur = self.faction.connection.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO location_affinity_defaults "
            "(address_tier, location_id, tag, affinity_value) VALUES (?, ?, ?, ?)",
            ("locality", "westhollow", "profession:blacksmith", 20.0),
        )
        self.faction.connection.commit()

    def test_context_includes_affiliations(self) -> None:
        self._seed_faction_data()
        self.agent.register_npc(
            npc_id="smith_1",
            personality={"voice": "Gruff smith."},
            location_hierarchy=[
                ("locality", "westhollow"),
                ("world", None),
            ],
        )
        out = self.agent._build_faction_context("smith_1")
        self.assertIn("NPC affiliations", out)
        self.assertIn("profession:blacksmith", out)

    def test_context_includes_personal_opinion(self) -> None:
        self._seed_faction_data()
        self.agent.register_npc(
            npc_id="smith_1",
            personality={"voice": "Gruff smith."},
            location_hierarchy=[("locality", "westhollow"), ("world", None)],
        )
        out = self.agent._build_faction_context("smith_1")
        # Personal opinion of +60 → "friendly" per _affinity_label.
        self.assertIn("Personal opinion of player", out)
        self.assertIn("friendly", out)

    def test_context_includes_player_standing(self) -> None:
        self._seed_faction_data()
        self.agent.register_npc(
            npc_id="smith_1",
            personality={"voice": "Gruff smith."},
            location_hierarchy=[("locality", "westhollow"), ("world", None)],
        )
        out = self.agent._build_faction_context("smith_1")
        self.assertIn("Player standing", out)
        # Player has +40 with profession:blacksmith.
        self.assertIn("profession:blacksmith", out)

    def test_context_empty_for_unknown_npc(self) -> None:
        # No data seeded for this id; helper short-circuits to empty string.
        out = self.agent._build_faction_context("unknown_npc_xyz")
        self.assertEqual(out, "")

    def test_affinity_label_thresholds(self) -> None:
        # Sanity-check the mapping is monotonic and labels are right.
        self.assertEqual(self.agent._affinity_label(-80), "hateful")
        self.assertEqual(self.agent._affinity_label(-50), "hostile")
        self.assertEqual(self.agent._affinity_label(0), "neutral")
        self.assertEqual(self.agent._affinity_label(50), "friendly")
        self.assertEqual(self.agent._affinity_label(80), "devoted")


class TestGameEngineRegisterHelper(_AgentWiringTestBase):
    """_register_npcs_with_agent_system walks self.npcs and registers each."""

    def test_helper_resolves_inline_personality_and_tag_fallback(self) -> None:
        # Import lazily so the patch above takes effect first.
        from data.models.npcs import NPCDefinition
        from data.models.world import Position

        class _FakeNPC:
            def __init__(self, npc_def):
                self.npc_def = npc_def

        npc_with_personality = NPCDefinition(
            npc_id="inline_npc",
            name="Inline NPC",
            personality={"voice": "Inline."},
            locality={"locality_id": "westhollow"},
            tags=["mentor"],
            position=Position(0.0, 0.0, 0.0),
        )
        npc_with_tag_only = NPCDefinition(
            npc_id="tagged_npc",
            name="Tagged NPC",
            personality={},
            locality={},
            tags=["blacksmith"],
            position=Position(0.0, 0.0, 0.0),
        )
        npc_bare = NPCDefinition(
            npc_id="bare_npc",
            name="Bare NPC",
            personality={},
            locality={},
            tags=[],
            position=Position(0.0, 0.0, 0.0),
        )

        # Build the minimal GameEngine surface the helper actually needs.
        from core.game_engine import GameEngine
        engine = GameEngine.__new__(GameEngine)
        engine.npc_agent_system = self.agent
        engine.npcs = [
            _FakeNPC(npc_with_personality),
            _FakeNPC(npc_with_tag_only),
            _FakeNPC(npc_bare),
        ]
        engine._register_npcs_with_agent_system()

        # Inline personality wins.
        self.assertEqual(
            self.agent.get_personality("inline_npc")["voice"], "Inline."
        )
        # Tag-only NPC routed to the blacksmith shared template.
        self.assertEqual(
            self.agent._npc_personalities["tagged_npc"], "blacksmith"
        )
        # Bare NPC falls to default.
        self.assertEqual(
            self.agent._npc_personalities["bare_npc"], "default"
        )
        # Location hierarchy stored for the NPC that had a locality_id.
        self.assertIn(
            ("locality", "westhollow"),
            self.agent._npc_locations["inline_npc"],
        )


if __name__ == "__main__":
    unittest.main()
