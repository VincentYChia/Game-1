"""Tests for Faction System Phase 3B: Quest Tool Integration.

Tests the quest_tool module for applying affinity deltas from quest outcomes.
"""

import os
import tempfile
from unittest.mock import patch

from events.event_bus import GameEventBus

from .faction_system import FACTION_AFFINITY_CHANGED, FactionSystem
from .quest_tool import QuestGenerator


class _QuestTestBase:
    """Shared setup/teardown for quest tests."""

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

        # Reset event bus
        GameEventBus.reset()
        self.event_bus = GameEventBus.get_instance()

    def teardown_method(self):
        FactionSystem.reset()
        GameEventBus.reset()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)


class TestQuestTool(_QuestTestBase):
    """Test QuestGenerator methods."""

    def test_get_affinity_deltas_smith_contract_honest(self):
        """Test affinity deltas for smith contract completion."""
        deltas = QuestGenerator.get_affinity_deltas("smith_contract", "complete_honestly")

        assert deltas == {
            "guild:smiths": 15.0,
            "nation:stormguard": 10.0,
            "profession:blacksmith": 8.0,
        }

    def test_get_affinity_deltas_smith_contract_dishonest(self):
        """Test affinity deltas for dishonest smithing."""
        deltas = QuestGenerator.get_affinity_deltas("smith_contract", "complete_dishonestly")

        assert deltas == {
            "guild:smiths": -20.0,
            "guild:thieves": 10.0,
            "rank:criminal": 5.0,
        }

    def test_get_affinity_deltas_unknown_quest(self):
        """Test that unknown quests return empty dict."""
        deltas = QuestGenerator.get_affinity_deltas("nonexistent_quest", "complete")
        assert deltas == {}

    def test_get_affinity_deltas_unknown_outcome(self):
        """Test that unknown outcomes return empty dict."""
        deltas = QuestGenerator.get_affinity_deltas("smith_contract", "nonexistent_outcome")
        assert deltas == {}

    def test_apply_quest_deltas_updates_affinities(self):
        """Test that deltas are correctly applied to player affinity."""
        deltas = {
            "guild:smiths": 15.0,
            "nation:stormguard": 10.0,
        }

        QuestGenerator.apply_quest_deltas("player_1", deltas)

        # Verify affinities were updated
        assert self.faction_sys.get_player_affinity("player_1", "guild:smiths") == 15.0
        assert self.faction_sys.get_player_affinity("player_1", "nation:stormguard") == 10.0

    def test_apply_quest_deltas_publishes_events(self):
        """Test that affinity changes publish events."""
        deltas = {
            "guild:smiths": 15.0,
            "nation:stormguard": 10.0,
        }

        # Record published events
        events = []
        self.event_bus.subscribe(
            FACTION_AFFINITY_CHANGED, lambda e: events.append(e)
        )

        QuestGenerator.apply_quest_deltas("player_1", deltas)

        # Should have published 2 events (one per tag)
        assert len(events) == 2
        assert events[0].event_type == FACTION_AFFINITY_CHANGED
        assert events[1].event_type == FACTION_AFFINITY_CHANGED

        # Verify event data
        event_data = [e.data for e in events]
        tags = {e["tag"] for e in event_data}
        assert tags == {"guild:smiths", "nation:stormguard"}

    def test_apply_quest_completion_combines_steps(self):
        """Test apply_quest_completion as convenience method."""
        applied = QuestGenerator.apply_quest_completion(
            "player_1", "smith_contract", "complete_honestly"
        )

        # Verify deltas were returned
        assert applied == {
            "guild:smiths": 15.0,
            "nation:stormguard": 10.0,
            "profession:blacksmith": 8.0,
        }

        # Verify affinity was updated
        assert self.faction_sys.get_player_affinity("player_1", "guild:smiths") == 15.0
        assert self.faction_sys.get_player_affinity("player_1", "profession:blacksmith") == 8.0

    def test_apply_quest_deltas_with_negative_values(self):
        """Test that negative deltas work correctly."""
        deltas = {
            "guild:smiths": -20.0,
            "guild:thieves": 10.0,
        }

        QuestGenerator.apply_quest_deltas("player_1", deltas)

        assert self.faction_sys.get_player_affinity("player_1", "guild:smiths") == -20.0
        assert self.faction_sys.get_player_affinity("player_1", "guild:thieves") == 10.0

    def test_apply_quest_deltas_incremental(self):
        """Test that multiple quest completions accumulate affinity."""
        # First quest
        QuestGenerator.apply_quest_completion(
            "player_1", "smith_contract", "complete_honestly"
        )
        assert self.faction_sys.get_player_affinity("player_1", "guild:smiths") == 15.0

        # Second quest (different type)
        deltas = {"guild:smiths": 10.0, "profession:merchant": 8.0}
        QuestGenerator.apply_quest_deltas("player_1", deltas)

        # guild:smiths should accumulate: 15 + 10 = 25
        assert self.faction_sys.get_player_affinity("player_1", "guild:smiths") == 25.0
        assert self.faction_sys.get_player_affinity("player_1", "profession:merchant") == 8.0

    def test_apply_quest_deltas_respects_clamping(self):
        """Test that affinity values clamp to -100..100."""
        # Set initial value
        self.faction_sys.set_player_affinity("player_1", "guild:smiths", 95.0)

        # Apply large delta
        QuestGenerator.apply_quest_deltas("player_1", {"guild:smiths": 20.0})

        # Should clamp at 100
        assert self.faction_sys.get_player_affinity("player_1", "guild:smiths") == 100.0
