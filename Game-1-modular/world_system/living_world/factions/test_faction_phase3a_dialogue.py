"""Tests for Faction System Phase 3A: Dialogue Integration.

Tests the dialogue_helper module and its integration with npc_agent.py.
"""

import os
import tempfile
from unittest.mock import patch

from events.event_bus import GameEventBus

from .dialogue_helper import assemble_dialogue_context
from .faction_system import FactionSystem
from .models import NPCProfile


class _DialogueTestBase:
    """Shared setup/teardown for dialogue tests."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_faction.db")

        with patch(
            "world_system.living_world.factions.faction_system.get_faction_db_path"
        ) as mock_path:
            mock_path.return_value = self.db_path
            FactionSystem.reset()
            self.faction_sys = FactionSystem.get_instance()
            self.faction_sys.initialize()

    def teardown_method(self):
        FactionSystem.reset()
        GameEventBus.reset()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)


class TestDialogueHelper(_DialogueTestBase):
    """Test dialogue_helper.assemble_dialogue_context()."""

    def test_assemble_dialogue_context_returns_required_keys(self):
        """Verify context dict has required keys."""
        # Setup test data
        self.faction_sys.add_npc("smith_1", "A master blacksmith", 0.0)
        self.faction_sys.add_npc_belonging_tag(
            "smith_1", "profession:blacksmith", 0.9
        )
        self.faction_sys.set_player_affinity("player_1", "profession:blacksmith", 30.0)

        # Assemble context
        context = assemble_dialogue_context(
            npc_id="smith_1",
            player_id="player_1",
            location_hierarchy=[
                ("locality", "westhollow"),
                ("district", "iron_hills"),
                ("nation", "nation:stormguard"),
                ("world", None),
            ],
        )

        # Verify required keys
        assert "npc" in context
        assert "player" in context
        assert "npc_opinion" in context
        assert "location" in context

    def test_assemble_dialogue_context_npc_profile_is_correct(self):
        """Verify NPC profile in context is accurate."""
        self.faction_sys.add_npc("npc_1", "Test NPC", 0.0)
        self.faction_sys.add_npc_belonging_tag("npc_1", "faction:test", 0.5)

        context = assemble_dialogue_context(
            npc_id="npc_1",
            player_id="player_1",
            location_hierarchy=[("world", None)],
        )

        npc = context["npc"]
        assert npc is not None
        assert npc.npc_id == "npc_1"
        assert npc.narrative == "Test NPC"
        assert "faction:test" in npc.belonging_tags

    def test_assemble_dialogue_context_player_affinity_included(self):
        """Verify player affinity data in context."""
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 40.0)
        self.faction_sys.set_player_affinity("player_1", "guild:merchants", -20.0)

        context = assemble_dialogue_context(
            npc_id="npc_1",
            player_id="player_1",
            location_hierarchy=[("world", None)],
        )

        player_data = context["player"]
        assert player_data["id"] == "player_1"
        assert "affinity_with_tags" in player_data
        assert player_data["affinity_with_tags"]["guild:smiths"] == 40.0
        assert player_data["affinity_with_tags"]["guild:merchants"] == -20.0

    def test_assemble_dialogue_context_npc_opinion_included(self):
        """Verify NPC's personal opinion of player."""
        self.faction_sys.add_npc("npc_1", "An NPC", 0.0)
        self.faction_sys.set_npc_affinity_toward_player("npc_1", 25.0)

        context = assemble_dialogue_context(
            npc_id="npc_1",
            player_id="player_1",
            location_hierarchy=[("world", None)],
        )

        assert context["npc_opinion"] == 25.0

    def test_assemble_dialogue_context_missing_npc_returns_none(self):
        """Verify context handles missing NPC gracefully."""
        context = assemble_dialogue_context(
            npc_id="nonexistent",
            player_id="player_1",
            location_hierarchy=[("world", None)],
        )

        assert context["npc"] is None

    def test_assemble_dialogue_context_location_hierarchy(self):
        """Verify location affinity inheritance with bootstrapped defaults."""
        # Defaults are bootstrapped at initialization
        # world: guild:merchants=10, guild:smiths=20, profession:guard=15, etc.
        # nation:stormguard: guild:smiths=30, profession:guard=40, profession:merchant=-15
        # district:iron_hills: guild:smiths=60, profession:blacksmith=50

        context = assemble_dialogue_context(
            npc_id="npc_1",
            player_id="player_1",
            location_hierarchy=[
                ("district", "district:iron_hills"),
                ("nation", "nation:stormguard"),
                ("world", None),
            ],
        )

        location_aff = context["location"]
        # Should sum inherited affinities from all hierarchy levels
        # guild:smiths: 60 (district) + 30 (nation) + 20 (world) = 110 → clamped to 100
        assert "guild:smiths" in location_aff
        assert location_aff["guild:smiths"] == 100.0  # Clamped at 100

        # profession:guard: 40 (nation) + 15 (world) = 55
        assert "profession:guard" in location_aff
        assert location_aff["profession:guard"] == 55.0

        # profession:blacksmith: 50 (district only)
        assert "profession:blacksmith" in location_aff
        assert location_aff["profession:blacksmith"] == 50.0
