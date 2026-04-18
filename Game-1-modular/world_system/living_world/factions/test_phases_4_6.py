"""Tests for Faction System Phases 4-6 (Dialogue, LLM, Advanced Features).

Tests the integration of:
- Phase 4: FactionDialogueGenerator (dialogue context building)
- Phase 5: LLM integration via BackendManager
- Phase 6: Affinity tiers, ripples, decay, milestones
"""

import pytest
import tempfile
import os
import time
from unittest.mock import Mock, patch, MagicMock

from world_system.living_world.factions.database import FactionDatabase
from world_system.living_world.factions.faction_dialogue_generator import FactionDialogueGenerator
from world_system.living_world.factions.affinity_features import (
    AffinityTierSystem,
    AffinityRippleSystem,
    AffinityDecayScheduler,
    AffinityMilestoneSystem,
)
from world_system.living_world.factions.models import NPCContextForDialogue, NPCBelongingTag


class TestFactionDialogueGenerator:
    """Test Phase 4: NPC dialogue context and generation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_faction.db")

        with patch("world_system.living_world.factions.database.get_faction_db_path") as mock_path:
            mock_path.return_value = self.db_path
            self.db = FactionDatabase.get_instance()
            self.db.initialize()

        self.generator = FactionDialogueGenerator()
        self.generator.initialize(self.db, backend=Mock())

    def teardown_method(self):
        """Clean up test database."""
        FactionDatabase.reset()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_build_npc_dialogue_context(self):
        """Test building complete dialogue context."""
        # Add NPC profile
        self.db.add_npc_profile(
            npc_id="smith_1",
            location_id="village_main",
            narrative="A skilled blacksmith.",
            primary_tag="profession:blacksmith"
        )
        self.db.add_npc_belonging_tag("smith_1", "profession:blacksmith", 85)
        self.db.add_npc_belonging_tag("smith_1", "nation:stormguard", 60)

        # Set player affinity
        self.db.add_player_affinity_delta("player", "profession:blacksmith", 25.0)
        self.db.add_player_affinity_delta("player", "nation:stormguard", -10.0)

        # Build context
        context = self.generator.build_npc_dialogue_context("smith_1", "player")

        # Assertions
        assert context is not None
        assert context.npc_id == "smith_1"
        assert context.npc_narrative == "A skilled blacksmith."
        assert len(context.npc_belonging_tags) == 2
        assert context.player_affinity["profession:blacksmith"] == 25.0
        assert context.player_affinity["nation:stormguard"] == -10.0

    def test_dialogue_context_missing_npc(self):
        """Test handling of missing NPC."""
        context = self.generator.build_npc_dialogue_context("nonexistent", "player")
        assert context is None

    def test_get_affinity_tier(self):
        """Test affinity value to tier mapping."""
        assert self.generator._get_affinity_tier(80.0) == "beloved"
        assert self.generator._get_affinity_tier(60.0) == "favored"
        assert self.generator._get_affinity_tier(30.0) == "respected"
        assert self.generator._get_affinity_tier(0.0) == "neutral"
        assert self.generator._get_affinity_tier(-30.0) == "disliked"
        assert self.generator._get_affinity_tier(-60.0) == "hated"
        assert self.generator._get_affinity_tier(-90.0) == "reviled"

    def test_compute_average_affinity(self):
        """Test average affinity calculation."""
        affinity = {"tag1": 50.0, "tag2": -20.0, "tag3": 30.0}
        avg = self.generator._compute_average_affinity(affinity)
        assert abs(avg - 20.0) < 0.01

    def test_dialogue_tone_mapping(self):
        """Test tone selection based on affinity."""
        # High affinity
        assert "Warm" in self.generator._get_dialogue_tone(60.0)
        # Neutral affinity
        assert "Neutral" in self.generator._get_dialogue_tone(5.0)
        # Low affinity
        assert "Hostile" in self.generator._get_dialogue_tone(-70.0)


class TestAffinityTierSystem:
    """Test Phase 6: Affinity tier mechanics."""

    def setup_method(self):
        """Set up tier system."""
        self.tier_system = AffinityTierSystem()

    def test_get_tier_name(self):
        """Test tier name retrieval."""
        assert self.tier_system.get_tier_name(80.0) == "beloved"
        assert self.tier_system.get_tier_name(60.0) == "favored"
        assert self.tier_system.get_tier_name(0.0) == "neutral"
        assert self.tier_system.get_tier_name(-30.0) == "disliked"

    def test_tier_special_interactions(self):
        """Test special interaction access."""
        # At beloved tier (75+)
        assert self.tier_system.can_access_interaction(80.0, "exclusive_quest")
        assert self.tier_system.can_access_interaction(80.0, "gift_access")

        # At favored tier (50-74)
        assert self.tier_system.can_access_interaction(60.0, "discount_trading")
        assert not self.tier_system.can_access_interaction(60.0, "exclusive_quest")

        # At neutral tier
        assert not self.tier_system.can_access_interaction(0.0, "discount_trading")

    def test_get_all_accessible_interactions(self):
        """Test getting all accessible interactions."""
        # At beloved (includes all lower tiers)
        interactions = self.tier_system.get_all_accessible_interactions(80.0)
        assert "exclusive_quest" in interactions
        assert "gift_access" in interactions
        # Beloved doesn't include favored's discount_trading
        assert "discount_trading" not in interactions

        # At favored
        interactions = self.tier_system.get_all_accessible_interactions(60.0)
        assert "discount_trading" in interactions


class TestAffinityRippleSystem:
    """Test Phase 6: Affinity propagation."""

    def setup_method(self):
        """Set up ripple system with mock database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_ripple.db")

        with patch("world_system.living_world.factions.database.get_faction_db_path") as mock_path:
            mock_path.return_value = self.db_path
            self.db = FactionDatabase.get_instance()
            self.db.initialize()

        self.ripple_system = AffinityRippleSystem()
        self.ripple_system.initialize(self.db)

    def teardown_method(self):
        """Clean up."""
        FactionDatabase.reset()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_ripple_propagation(self):
        """Test affinity ripples to related tags."""
        # Apply delta to source tag
        self.ripple_system.apply_ripples("player", "guild:smiths", 10.0)

        # Check ripple effects
        # guild:crafters should get ~3.0 (10 * 0.3)
        crafter_aff = self.db.get_player_affinity("player", "guild:crafters")
        assert 2.9 < crafter_aff < 3.1

        # nation:stormguard should get ~1.0 (10 * 0.1)
        nation_aff = self.db.get_player_affinity("player", "nation:stormguard")
        assert 0.9 < nation_aff < 1.1

    def test_add_ripple_relationship(self):
        """Test adding new ripple relationships at runtime."""
        self.ripple_system.add_ripple_relationship("custom_tag", "target_tag", 0.5)
        assert ("target_tag", 0.5) in self.ripple_system.ripple_map["custom_tag"]


class TestAffinityDecayScheduler:
    """Test Phase 6: Time-based decay."""

    def setup_method(self):
        """Set up decay scheduler with mock database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_decay.db")

        with patch("world_system.living_world.factions.database.get_faction_db_path") as mock_path:
            mock_path.return_value = self.db_path
            self.db = FactionDatabase.get_instance()
            self.db.initialize()

        self.scheduler = AffinityDecayScheduler()
        self.scheduler.initialize(self.db)
        self.scheduler._check_interval = 0.1  # Speed up for testing

    def teardown_method(self):
        """Clean up."""
        self.scheduler.stop()
        FactionDatabase.reset()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_decay_starts_and_stops(self):
        """Test scheduler lifecycle."""
        assert not self.scheduler._running
        self.scheduler.start()
        assert self.scheduler._running
        self.scheduler.stop()
        assert not self.scheduler._running

    def test_soft_decay_toward_zero(self):
        """Test that decay approaches zero without crossing."""
        # Set positive affinity
        self.db.add_player_affinity_delta("player", "test_tag", 10.0)
        aff_before = self.db.get_player_affinity("player", "test_tag")
        assert aff_before == 10.0

        # Apply decay manually
        self.scheduler._apply_decay_to_all_affinities("player", -0.1)
        aff_after = self.db.get_player_affinity("player", "test_tag")

        # Should decrease but still be positive
        assert 9.8 < aff_after < 10.0

        # Repeatedly decay to near zero
        for _ in range(100):
            self.scheduler._apply_decay_to_all_affinities("player", -0.1)
        final_aff = self.db.get_player_affinity("player", "test_tag")
        assert 0.0 <= final_aff < 0.5


class TestAffinityMilestoneSystem:
    """Test Phase 6: Milestone tracking and events."""

    def setup_method(self):
        """Set up milestone system."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_milestone.db")

        with patch("world_system.living_world.factions.database.get_faction_db_path") as mock_path:
            mock_path.return_value = self.db_path
            self.db = FactionDatabase.get_instance()
            self.db.initialize()

        self.event_bus = Mock()
        self.milestone_system = AffinityMilestoneSystem()
        self.milestone_system.initialize(self.db, self.event_bus)

    def teardown_method(self):
        """Clean up."""
        FactionDatabase.reset()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_milestone_crossing_detection(self):
        """Test detection of milestone threshold crossing."""
        # Cross from neutral (0) to favored (50+)
        self.milestone_system.check_milestone("player", "test_tag", 51.0)

        # Should publish event
        self.event_bus.publish.assert_called_once()
        call_args = self.event_bus.publish.call_args
        assert call_args[0][0] == "AFFINITY_MILESTONE"
        event_data = call_args[0][1]
        assert event_data["milestone"] == "favored"
        assert event_data["direction"] == "reached"

    def test_milestone_not_repeated(self):
        """Test that milestones don't repeat within same tier."""
        self.event_bus.reset_mock()

        # Reach favored
        self.milestone_system.check_milestone("player", "test_tag", 51.0)
        call_count_1 = self.event_bus.publish.call_count

        # Move within same tier
        self.milestone_system.check_milestone("player", "test_tag", 60.0)
        call_count_2 = self.event_bus.publish.call_count

        # Should not have published again
        assert call_count_1 == call_count_2


class TestIntegration:
    """Integration tests for all Phase 4-6 systems working together."""

    def setup_method(self):
        """Set up full integration test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_integration.db")

        with patch("world_system.living_world.factions.database.get_faction_db_path") as mock_path:
            mock_path.return_value = self.db_path
            self.db = FactionDatabase.get_instance()
            self.db.initialize()

        # Initialize all systems
        self.dialogue_gen = FactionDialogueGenerator()
        self.dialogue_gen.initialize(self.db, backend=Mock())

        self.tier_system = AffinityTierSystem()

        self.ripple_system = AffinityRippleSystem()
        self.ripple_system.initialize(self.db)

        self.event_bus = Mock()
        self.milestone_system = AffinityMilestoneSystem()
        self.milestone_system.initialize(self.db, self.event_bus)

    def teardown_method(self):
        """Clean up."""
        FactionDatabase.reset()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_full_affinity_change_flow(self):
        """Test complete flow: change → ripple → milestone → tier check."""
        # Add NPC
        self.db.add_npc_profile("npc1", "loc1", "A merchant", "profession:merchant")
        self.db.add_npc_belonging_tag("npc1", "profession:merchant", 70)
        self.db.add_npc_belonging_tag("npc1", "guild:merchants", 85)

        # 1. Apply affinity change
        delta = 30.0
        self.db.add_player_affinity_delta("player", "guild:merchants", delta)
        aff = self.db.get_player_affinity("player", "guild:merchants")
        assert aff == 30.0

        # 2. Apply ripples
        self.ripple_system.apply_ripples("player", "guild:merchants", delta)
        ripple_aff = self.db.get_player_affinity("player", "guild:crafters")
        assert ripple_aff > 0  # Should have rippled

        # 3. Check milestones
        self.milestone_system.check_milestone("player", "guild:merchants", aff)
        self.event_bus.publish.assert_called_once()

        # 4. Check tier
        tier_name = self.tier_system.get_tier_name(aff)
        assert tier_name == "respected"

        # 5. Build dialogue context
        context = self.dialogue_gen.build_npc_dialogue_context("npc1", "player")
        assert context.player_affinity["guild:merchants"] == 30.0
        assert context.npc_belonging_tags[0].tag == "profession:merchant"
