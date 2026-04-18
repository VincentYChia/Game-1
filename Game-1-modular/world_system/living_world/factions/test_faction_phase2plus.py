"""Tests for Faction System Phase 2+.

Tests the complete faction recording and retrieval system:
- NPC profiles with belonging tags and affinity toward tags
- Player affinity tracking (-100 to 100)
- NPC affinity toward the player (stored in npc_affinity under reserved tag)
- Location affinity defaults with hierarchical inheritance
- FACTION_AFFINITY_CHANGED event publication
"""

import os
import tempfile
from unittest.mock import patch

from events.event_bus import GameEventBus, get_event_bus

from .faction_system import FACTION_AFFINITY_CHANGED, FactionSystem
from .schema import NPC_AFFINITY_PLAYER_TAG


class _FactionTestBase:
    """Shared setup/teardown — uses a temp SQLite file per test."""

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


class TestNPCProfiles(_FactionTestBase):
    """Test NPC profile operations."""

    def test_add_and_retrieve_npc(self):
        self.faction_sys.add_npc("smith_1", "A master blacksmith from the north", 0.0)

        profile = self.faction_sys.get_npc_profile("smith_1")
        assert profile is not None
        assert profile.npc_id == "smith_1"
        assert profile.narrative == "A master blacksmith from the north"

    def test_add_npc_belonging_tag(self):
        self.faction_sys.add_npc("smith_1", "A blacksmith", 0.0)
        self.faction_sys.add_npc_belonging_tag(
            "smith_1",
            "profession:blacksmith",
            0.8,
            role="master",
            narrative_hooks=["Skilled craftsperson", "Respected locally"],
        )

        tags = self.faction_sys.get_npc_belonging_tags("smith_1")
        assert len(tags) == 1
        assert tags[0].tag == "profession:blacksmith"
        assert tags[0].significance == 0.8
        assert tags[0].role == "master"
        assert tags[0].narrative_hooks == ["Skilled craftsperson", "Respected locally"]

    def test_get_all_npcs_with_tag(self):
        self.faction_sys.add_npc("smith_1", "Smith 1", 0.0)
        self.faction_sys.add_npc("smith_2", "Smith 2", 0.0)
        self.faction_sys.add_npc("merchant_1", "Merchant 1", 0.0)

        self.faction_sys.add_npc_belonging_tag("smith_1", "guild:smiths", 0.7)
        self.faction_sys.add_npc_belonging_tag("smith_2", "guild:smiths", 0.6)
        self.faction_sys.add_npc_belonging_tag("merchant_1", "guild:merchants", 0.8)

        smiths = self.faction_sys.get_all_npcs_with_tag("guild:smiths")
        assert len(smiths) == 2
        assert set(smiths) == {"smith_1", "smith_2"}


class TestPlayerAffinity(_FactionTestBase):
    """Test player affinity operations."""

    def test_set_and_get_player_affinity(self):
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 50.0)
        assert self.faction_sys.get_player_affinity("player_1", "guild:smiths") == 50.0

    def test_adjust_player_affinity(self):
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 40.0)
        new_aff = self.faction_sys.adjust_player_affinity(
            "player_1", "guild:smiths", 15.0
        )
        assert new_aff == 55.0

    def test_affinity_clamping(self):
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 150.0)
        assert self.faction_sys.get_player_affinity("player_1", "guild:smiths") == 100.0

        self.faction_sys.set_player_affinity("player_1", "guild:smiths", -200.0)
        assert self.faction_sys.get_player_affinity("player_1", "guild:smiths") == -100.0

    def test_get_all_player_affinities(self):
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 30.0)
        self.faction_sys.set_player_affinity("player_1", "guild:merchants", -20.0)
        self.faction_sys.set_player_affinity("player_1", "nation:stormguard", 50.0)

        affs = self.faction_sys.get_all_player_affinities("player_1")
        assert len(affs) == 3
        assert affs["guild:smiths"] == 30.0
        assert affs["guild:merchants"] == -20.0


class TestNPCAffinityTowardPlayer(_FactionTestBase):
    """NPC personal opinion of the player — stored in npc_affinity under
    the reserved tag, not in a separate table."""

    def test_default_is_zero(self):
        self.faction_sys.add_npc("npc_1", "Someone", 0.0)
        assert self.faction_sys.get_npc_affinity_toward_player("npc_1") == 0.0

    def test_set_and_get(self):
        self.faction_sys.add_npc("npc_1", "Someone", 0.0)
        self.faction_sys.set_npc_affinity_toward_player("npc_1", 25.0)
        assert self.faction_sys.get_npc_affinity_toward_player("npc_1") == 25.0

    def test_adjust(self):
        self.faction_sys.add_npc("npc_1", "Someone", 0.0)
        self.faction_sys.set_npc_affinity_toward_player("npc_1", 10.0)
        new_val = self.faction_sys.adjust_npc_affinity_toward_player("npc_1", -15.0)
        assert new_val == -5.0

    def test_stored_in_npc_affinity_table(self):
        """Verify the user's directive: no separate table, uses reserved tag."""
        self.faction_sys.add_npc("npc_1", "Someone", 0.0)
        self.faction_sys.set_npc_affinity_toward_player("npc_1", 30.0)

        # Same value readable via the generic npc_affinity accessor
        assert (
            self.faction_sys.get_npc_affinity("npc_1", NPC_AFFINITY_PLAYER_TAG) == 30.0
        )

    def test_does_not_collide_with_tag_affinity(self):
        self.faction_sys.add_npc("npc_1", "Someone", 0.0)
        self.faction_sys.set_npc_affinity("npc_1", "guild:smiths", 70.0)
        self.faction_sys.set_npc_affinity_toward_player("npc_1", -20.0)

        assert self.faction_sys.get_npc_affinity("npc_1", "guild:smiths") == 70.0
        assert self.faction_sys.get_npc_affinity_toward_player("npc_1") == -20.0


class TestLocationAffinity(_FactionTestBase):
    """Location affinity defaults and hierarchical inheritance."""

    def test_bootstrap_defaults_loaded(self):
        defaults = self.faction_sys.get_location_affinity_defaults(
            "nation", "nation:stormguard"
        )
        assert len(defaults) > 0
        assert defaults.get("guild:smiths", 0.0) > 0.0

    def test_world_tier_uses_null_location(self):
        defaults = self.faction_sys.get_location_affinity_defaults("world", None)
        assert len(defaults) > 0
        assert "guild:smiths" in defaults

    def test_compute_inherited_affinity_sums(self):
        hierarchy = [
            ("district", "district:iron_hills"),
            ("nation", "nation:stormguard"),
            ("world", None),
        ]
        accumulated = self.faction_sys.compute_inherited_affinity(hierarchy)
        # world (20) + nation (30) + district (60) = 100 (clamped to 100)
        assert accumulated["guild:smiths"] == 100.0

    def test_inheritance_clamps_at_100(self):
        hierarchy = [
            ("district", "district:iron_hills"),
            ("nation", "nation:stormguard"),
            ("world", None),
        ]
        accumulated = self.faction_sys.compute_inherited_affinity(hierarchy)
        for value in accumulated.values():
            assert -100.0 <= value <= 100.0


class TestEventPublishing(_FactionTestBase):
    """adjust_player_affinity and set_player_affinity must publish
    FACTION_AFFINITY_CHANGED for the WMS evaluator to consume."""

    def setup_method(self):
        super().setup_method()
        self.events = []
        get_event_bus().subscribe(
            FACTION_AFFINITY_CHANGED, lambda e: self.events.append(e)
        )

    def test_adjust_publishes_event(self):
        self.faction_sys.adjust_player_affinity("player_1", "guild:smiths", 15.0)

        assert len(self.events) == 1
        evt = self.events[0]
        assert evt.event_type == FACTION_AFFINITY_CHANGED
        assert evt.data["player_id"] == "player_1"
        assert evt.data["tag"] == "guild:smiths"
        assert evt.data["delta"] == 15.0
        assert evt.data["new_value"] == 15.0
        assert evt.data["source"] == "adjust"

    def test_set_publishes_delta(self):
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 40.0)
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 60.0)

        assert len(self.events) == 2
        assert self.events[0].data["delta"] == 40.0
        assert self.events[1].data["delta"] == 20.0

    def test_no_event_when_value_unchanged(self):
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 40.0)
        self.events.clear()

        self.faction_sys.adjust_player_affinity("player_1", "guild:smiths", 0.0)
        assert len(self.events) == 0

    def test_event_delta_reflects_clamping(self):
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 95.0)
        self.events.clear()

        # Requested +50 but clamp to 100, so actual delta is +5
        self.faction_sys.adjust_player_affinity("player_1", "guild:smiths", 50.0)
        assert len(self.events) == 1
        assert self.events[0].data["delta"] == 5.0
        assert self.events[0].data["new_value"] == 100.0


class TestIntegration(_FactionTestBase):
    """End-to-end workflow: quest-style affinity application."""

    def test_quest_completion_workflow(self):
        """Quest system provides deltas; FactionSystem records them."""
        self.faction_sys.add_npc("smith_1", "Master Smith", 0.0)
        self.faction_sys.add_npc_belonging_tag("smith_1", "guild:smiths", 0.8)
        self.faction_sys.add_npc_belonging_tag("smith_1", "profession:blacksmith", 0.9)

        tags = self.faction_sys.get_npc_belonging_tags("smith_1")
        tag_names = [t.tag for t in tags]

        deltas = {tag: 10.0 for tag in tag_names}
        for tag, delta in deltas.items():
            self.faction_sys.adjust_player_affinity("player_1", tag, delta)

        assert self.faction_sys.get_player_affinity("player_1", "guild:smiths") == 10.0
        assert (
            self.faction_sys.get_player_affinity("player_1", "profession:blacksmith")
            == 10.0
        )
