"""Tests for Faction System Phases 2+.

Tests the complete faction recording and retrieval system:
- NPC profiles with belonging tags and affinity
- Player affinity tracking (-100 to 100)
- Location affinity defaults with inheritance
- Reputation rules engine
"""

import pytest
import tempfile
import os
from unittest.mock import patch

from .faction_system import FactionSystem
from .models import NPCProfile, PlayerProfile, FactionTag
from .schema import FactionDatabaseSchema


class TestNPCProfiles:
    """Test NPC profile operations."""

    def setup_method(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_faction.db")

        with patch("world_system.living_world.factions.faction_system.get_faction_db_path") as mock_path:
            mock_path.return_value = self.db_path
            self.faction_sys = FactionSystem.get_instance()
            self.faction_sys.initialize()

    def teardown_method(self):
        """Clean up test database."""
        FactionSystem.reset()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_add_and_retrieve_npc(self):
        """Test adding and retrieving NPC profile."""
        self.faction_sys.add_npc("smith_1", "A master blacksmith from the north", 0.0)

        profile = self.faction_sys.get_npc_profile("smith_1")
        assert profile is not None
        assert profile.npc_id == "smith_1"
        assert profile.narrative == "A master blacksmith from the north"

    def test_add_npc_belonging_tag(self):
        """Test adding belonging tags to NPC."""
        self.faction_sys.add_npc("smith_1", "A blacksmith", 0.0)
        self.faction_sys.add_npc_belonging_tag(
            "smith_1",
            "profession:blacksmith",
            0.8,
            role="master",
            narrative_hooks=["Skilled craftsperson", "Respected locally"]
        )

        tags = self.faction_sys.get_npc_belonging_tags("smith_1")
        assert len(tags) == 1
        assert tags[0].tag == "profession:blacksmith"
        assert tags[0].significance == 0.8
        assert tags[0].role == "master"

    def test_get_all_npcs_with_tag(self):
        """Test querying NPCs by tag."""
        self.faction_sys.add_npc("smith_1", "Smith 1", 0.0)
        self.faction_sys.add_npc("smith_2", "Smith 2", 0.0)
        self.faction_sys.add_npc("merchant_1", "Merchant 1", 0.0)

        self.faction_sys.add_npc_belonging_tag("smith_1", "guild:smiths", 0.7)
        self.faction_sys.add_npc_belonging_tag("smith_2", "guild:smiths", 0.6)
        self.faction_sys.add_npc_belonging_tag("merchant_1", "guild:merchants", 0.8)

        smiths = self.faction_sys.get_all_npcs_with_tag("guild:smiths")
        assert len(smiths) == 2
        assert "smith_1" in smiths
        assert "smith_2" in smiths


class TestPlayerAffinity:
    """Test player affinity operations."""

    def setup_method(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_faction.db")

        with patch("world_system.living_world.factions.faction_system.get_faction_db_path") as mock_path:
            mock_path.return_value = self.db_path
            self.faction_sys = FactionSystem.get_instance()
            self.faction_sys.initialize()

    def teardown_method(self):
        """Clean up test database."""
        FactionSystem.reset()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_set_and_get_player_affinity(self):
        """Test setting and retrieving player affinity."""
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 50.0)

        aff = self.faction_sys.get_player_affinity("player_1", "guild:smiths")
        assert aff == 50.0

    def test_adjust_player_affinity(self):
        """Test adjusting player affinity."""
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 40.0)
        new_aff = self.faction_sys.adjust_player_affinity("player_1", "guild:smiths", 15.0)

        assert new_aff == 55.0

    def test_affinity_clamping(self):
        """Test that affinity is clamped to -100/100."""
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 150.0)
        aff = self.faction_sys.get_player_affinity("player_1", "guild:smiths")
        assert aff == 100.0

        self.faction_sys.set_player_affinity("player_1", "guild:smiths", -200.0)
        aff = self.faction_sys.get_player_affinity("player_1", "guild:smiths")
        assert aff == -100.0

    def test_get_all_player_affinities(self):
        """Test retrieving all player affinities."""
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 30.0)
        self.faction_sys.set_player_affinity("player_1", "guild:merchants", -20.0)
        self.faction_sys.set_player_affinity("player_1", "nation:stormguard", 50.0)

        affs = self.faction_sys.get_all_player_affinities("player_1")
        assert len(affs) == 3
        assert affs["guild:smiths"] == 30.0
        assert affs["guild:merchants"] == -20.0


class TestLocationAffinity:
    """Test location affinity defaults and inheritance."""

    def setup_method(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_faction.db")

        with patch("world_system.living_world.factions.faction_system.get_faction_db_path") as mock_path:
            mock_path.return_value = self.db_path
            self.faction_sys = FactionSystem.get_instance()
            self.faction_sys.initialize()

    def teardown_method(self):
        """Clean up test database."""
        FactionSystem.reset()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_get_location_affinity_defaults(self):
        """Test retrieving affinity defaults for a location."""
        defaults = self.faction_sys.get_location_affinity_defaults("nation", "nation:stormguard")
        # Should have bootstrap data
        assert len(defaults) > 0
        # Smiths should be high affinity in stormguard
        assert defaults.get("guild:smiths", 0.0) > 0.0

    def test_compute_inherited_affinity(self):
        """Test computing accumulated affinity through hierarchy."""
        # Build a hierarchy: world → nation → district → locality
        hierarchy = [
            ("locality", "village_westhollow"),
            ("district", "grain_fields"),
            ("nation", "nation:stormguard"),
            ("world", None),
        ]

        accumulated = self.faction_sys.compute_inherited_affinity(hierarchy)
        # Should sum all defaults along the path
        assert len(accumulated) > 0


class TestIntegration:
    """Integration tests combining multiple systems."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_faction.db")

        with patch("world_system.living_world.factions.faction_system.get_faction_db_path") as mock_path:
            mock_path.return_value = self.db_path
            self.faction_sys = FactionSystem.get_instance()
            self.faction_sys.initialize()

    def teardown_method(self):
        """Clean up."""
        FactionSystem.reset()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_quest_completion_workflow(self):
        """Test complete quest completion → affinity flow.

        In the actual system, the quest system provides deltas directly.
        This test simulates that by applying deltas manually.
        """
        # Create NPC
        self.faction_sys.add_npc("smith_1", "Master Smith", 0.0)
        self.faction_sys.add_npc_belonging_tag("smith_1", "guild:smiths", 0.8)
        self.faction_sys.add_npc_belonging_tag("smith_1", "profession:blacksmith", 0.9)

        # Get NPC's tags
        tags = self.faction_sys.get_npc_belonging_tags("smith_1")
        tag_names = [t.tag for t in tags]

        # Simulate quest providing deltas (in reality, quest system provides these)
        deltas = {tag: 10.0 for tag in tag_names}

        # Apply deltas to player affinity
        for tag, delta in deltas.items():
            self.faction_sys.adjust_player_affinity("player_1", tag, delta)

        # Verify player affinity updated
        smith_aff = self.faction_sys.get_player_affinity("player_1", "guild:smiths")
        assert smith_aff == 10.0

        blacksmith_aff = self.faction_sys.get_player_affinity("player_1", "profession:blacksmith")
        assert blacksmith_aff == 10.0
