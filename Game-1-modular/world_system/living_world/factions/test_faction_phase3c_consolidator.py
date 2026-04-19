"""Tests for Faction System Phase 3C: Affinity Consolidator.

Tests the consolidator module for rolling up affinity data into
narrative-friendly summaries.
"""

import os
import tempfile
from unittest.mock import patch

from events.event_bus import GameEventBus, get_event_bus

from .consolidator import (
    FACTION_AFFINITY_CONSOLIDATED,
    AffinityConsolidator,
)
from .faction_system import FactionSystem


class _ConsolidatorTestBase:
    """Shared setup/teardown for consolidator tests."""

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

        GameEventBus.reset()

    def teardown_method(self):
        FactionSystem.reset()
        GameEventBus.reset()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)


class TestConsolidator(_ConsolidatorTestBase):
    """Test AffinityConsolidator methods."""

    def test_consolidate_player_standing_empty(self):
        """Test consolidation with no affinities."""
        standing = AffinityConsolidator.consolidate_player_standing("player_1")
        assert standing == {}

    def test_consolidate_player_standing_single_affinity(self):
        """Test consolidation with one affinity."""
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 50.0)

        standing = AffinityConsolidator.consolidate_player_standing("player_1")
        assert standing == {"guild:smiths": 50.0}

    def test_consolidate_player_standing_multiple_affinities(self):
        """Test consolidation with multiple affinities."""
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 75.0)
        self.faction_sys.set_player_affinity("player_1", "nation:stormguard", 60.0)
        self.faction_sys.set_player_affinity("player_1", "guild:merchants", -40.0)
        self.faction_sys.set_player_affinity("player_1", "profession:guard", 30.0)
        self.faction_sys.set_player_affinity("player_1", "rank:hero", 20.0)

        standing = AffinityConsolidator.consolidate_player_standing("player_1")

        # Should return top 5 by absolute value
        assert len(standing) == 5
        assert standing["guild:smiths"] == 75.0
        assert standing["nation:stormguard"] == 60.0
        assert standing["guild:merchants"] == -40.0

    def test_consolidate_player_standing_respects_top_5(self):
        """Test that only top 5 are returned."""
        for i in range(10):
            self.faction_sys.set_player_affinity(
                "player_1", f"tag:tag{i}", float(100 - i * 5)
            )

        standing = AffinityConsolidator.consolidate_player_standing("player_1")
        assert len(standing) == 5

    def test_consolidate_player_standing_filters_zeros(self):
        """Test that zero values are filtered out."""
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 50.0)
        self.faction_sys.set_player_affinity("player_1", "guild:merchants", 0.0)
        self.faction_sys.set_player_affinity("player_1", "nation:stormguard", 30.0)

        standing = AffinityConsolidator.consolidate_player_standing("player_1")

        # guild:merchants should not appear (zero value)
        assert "guild:merchants" not in standing
        assert len(standing) == 2

    def test_consolidate_player_standing_sorted_by_absolute_value(self):
        """Test that results are sorted by absolute value descending."""
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 30.0)
        self.faction_sys.set_player_affinity("player_1", "guild:merchants", -75.0)
        self.faction_sys.set_player_affinity("player_1", "nation:stormguard", 50.0)

        standing = AffinityConsolidator.consolidate_player_standing("player_1")
        values = list(standing.values())

        # Should be ordered: |-75|, 50, 30 → -75, 50, 30
        assert values[0] == -75.0
        assert values[1] == 50.0
        assert values[2] == 30.0

    def test_get_player_reputation_summary_empty(self):
        """Test reputation summary with no affinities."""
        summary = AffinityConsolidator.get_player_reputation_summary("player_1")
        assert summary == "Unknown reputation"

    def test_get_player_reputation_summary_high_affinity(self):
        """Test reputation summary with positive affinities."""
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 75.0)
        self.faction_sys.set_player_affinity("player_1", "nation:stormguard", 60.0)

        summary = AffinityConsolidator.get_player_reputation_summary("player_1")
        assert "revered" in summary
        assert "guild:smiths" in summary or "nation:stormguard" in summary

    def test_get_player_reputation_summary_negative_affinity(self):
        """Test reputation summary with negative affinities."""
        self.faction_sys.set_player_affinity("player_1", "guild:merchants", -60.0)

        summary = AffinityConsolidator.get_player_reputation_summary("player_1")
        assert "distrusted" in summary
        assert "guild:merchants" in summary

    def test_publish_consolidated_event_succeeds(self):
        """Test that consolidated event publishes without error."""
        summary = {"guild:smiths": 50.0, "nation:stormguard": 30.0}

        # Should not raise
        AffinityConsolidator.publish_consolidated_event("player_1", summary)

    def test_publish_consolidated_event_contains_correct_data(self):
        """Test that published event contains correct data."""
        summary = {"guild:smiths": 50.0}
        events = []

        get_event_bus().subscribe(
            FACTION_AFFINITY_CONSOLIDATED, lambda e: events.append(e)
        )

        AffinityConsolidator.publish_consolidated_event("player_1", summary)

        assert len(events) == 1
        evt = events[0]
        assert evt.event_type == FACTION_AFFINITY_CONSOLIDATED
        assert evt.data["player_id"] == "player_1"
        assert evt.data["top_affinities"] == summary

    def test_consolidate_and_publish_combines_steps(self):
        """Test convenience method."""
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 75.0)
        self.faction_sys.set_player_affinity("player_1", "nation:stormguard", 50.0)

        events = []
        get_event_bus().subscribe(
            FACTION_AFFINITY_CONSOLIDATED, lambda e: events.append(e)
        )

        standing = AffinityConsolidator.consolidate_and_publish("player_1")

        # Verify standing returned
        assert standing == {"guild:smiths": 75.0, "nation:stormguard": 50.0}

        # Verify event published
        assert len(events) == 1
        assert events[0].data["top_affinities"] == standing

    def test_consolidate_and_publish_no_event_when_empty(self):
        """Test that no event is published when standing is empty."""
        events = []
        get_event_bus().subscribe(
            FACTION_AFFINITY_CONSOLIDATED, lambda e: events.append(e)
        )

        standing = AffinityConsolidator.consolidate_and_publish("player_1")

        assert standing == {}
        # No event should be published for empty standing
        assert len(events) == 0
