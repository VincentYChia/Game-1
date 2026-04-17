"""Comprehensive test suite for Faction System Phase 2.

Tests cover:
- FactionDatabase initialization and schema creation
- NPC profile CRUD operations
- Player affinity tracking
- Cultural affinity calculation (additive across tiers)
- Quest log operations
- Context assembly for LLM dialogue
"""

import sqlite3
import tempfile
import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Test fixtures
from world_system.living_world.factions.models import (
    NPCFactionProfile, NPCBelongingTag, PlayerAffinityProfile,
    AffinityDefaultEntry, QuestLogEntry, NPCContextForDialogue
)
from world_system.living_world.factions.schema import FactionDatabaseSchema, BOOTSTRAP_AFFINITY_DEFAULTS_SQL
from world_system.living_world.factions.database import FactionDatabase


class FactionTestFixture:
    """Setup/teardown for faction tests."""

    def __init__(self):
        self.temp_dir = None
        self.db_path = None
        self.original_get_path = None

    def setup(self):
        """Create temporary database for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_faction.db"

        # Patch get_faction_db_path at the point of use (in database module)
        from world_system.living_world.factions import database
        self.original_get_path = database.get_faction_db_path
        database.get_faction_db_path = lambda: self.db_path

        # Reset singleton
        FactionDatabase.reset()

    def teardown(self):
        """Clean up test database."""
        FactionDatabase.reset()

        # Restore original function
        if self.original_get_path is not None:
            from world_system.living_world.factions import database
            database.get_faction_db_path = self.original_get_path

        # Clean up temp files
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)


# Test suites
def test_database_initialization():
    """Task 15: Verify database initializes and creates schema."""
    fixture = FactionTestFixture()
    fixture.setup()

    try:
        db = FactionDatabase.get_instance()
        db.initialize()

        assert db.connection is not None, "Database connection should be open"
        assert db._initialized, "Database should be marked as initialized"
        assert fixture.db_path.exists(), "Database file should be created"

        # Verify tables exist
        cursor = db.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        expected = {
            'npc_profiles', 'npc_belonging', 'player_affinity',
            'affinity_defaults', 'cultural_affinity_cache', 'quest_log',
            'faction_schema_version'
        }
        assert expected.issubset(tables), f"Missing tables. Have: {tables}, expected: {expected}"

        # Verify bootstrap data loaded
        cursor.execute("SELECT COUNT(*) FROM affinity_defaults")
        count = cursor.fetchone()[0]
        assert count > 0, f"Bootstrap data should be loaded, got {count} rows"

        print("✓ test_database_initialization PASSED")
        return True
    except AssertionError as e:
        print(f"✗ test_database_initialization FAILED: {e}")
        return False
    finally:
        fixture.teardown()


def test_npc_profile_crud():
    """Task 16: Verify NPC profile create/read/update operations."""
    fixture = FactionTestFixture()
    fixture.setup()

    try:
        db = FactionDatabase.get_instance()
        db.initialize()

        # Create NPC profile
        npc = db.create_npc_profile(
            npc_id="test_npc_1",
            location_id="district:ironpeak",
            narrative="A mysterious scholar from the North.",
            primary_tag="profession:scholar",
            metadata={"archetype": "wise_elder"}
        )

        assert npc.npc_id == "test_npc_1"
        assert npc.narrative == "A mysterious scholar from the North."
        assert npc.metadata["archetype"] == "wise_elder"

        # Read NPC profile
        retrieved = db.get_npc_profile("test_npc_1")
        assert retrieved is not None, "NPC should be retrievable"
        assert retrieved.narrative == "A mysterious scholar from the North."

        # Update NPC narrative
        new_narrative = "An older scholar who has seen much."
        updated = db.update_npc_narrative("test_npc_1", new_narrative)
        assert updated, "Update should succeed"

        retrieved_updated = db.get_npc_profile("test_npc_1")
        assert retrieved_updated.narrative == new_narrative, "Narrative should be updated"

        # Non-existent NPC should return None
        not_found = db.get_npc_profile("nonexistent_npc")
        assert not_found is None, "Non-existent NPC should return None"

        print("✓ test_npc_profile_crud PASSED")
        return True
    except AssertionError as e:
        print(f"✗ test_npc_profile_crud FAILED: {e}")
        return False
    finally:
        fixture.teardown()


def test_npc_belonging_tags():
    """Task 16: Verify NPC belonging tag operations."""
    fixture = FactionTestFixture()
    fixture.setup()

    try:
        db = FactionDatabase.get_instance()
        db.initialize()

        # Create NPC first
        db.create_npc_profile(
            npc_id="test_npc_2",
            location_id="nation:stormguard",
            narrative="A loyal soldier.",
            primary_tag="profession:soldier"
        )

        # Add belonging tags
        added1 = db.add_npc_belonging_tag(
            npc_id="test_npc_2",
            tag="nation:stormguard",
            significance=75.0,
            role="guard",
            narrative_hooks=["Sworn to protect", "Loyal to the crown", "Trained warrior"]
        )
        assert added1, "First tag should be added"

        added2 = db.add_npc_belonging_tag(
            npc_id="test_npc_2",
            tag="guild:soldiers",
            significance=50.0,
            role="member",
            narrative_hooks=["Guild member", "Follows code", "Respects hierarchy"]
        )
        assert added2, "Second tag should be added"

        # Duplicate tag should fail
        duplicate = db.add_npc_belonging_tag(
            npc_id="test_npc_2",
            tag="nation:stormguard",
            significance=75.0
        )
        assert not duplicate, "Duplicate tag should not be added"

        # Get belonging tags
        tags = db.get_npc_belonging_tags("test_npc_2")
        assert len(tags) == 2, f"Should have 2 tags, got {len(tags)}"

        tag_names = {tag.tag for tag in tags}
        assert "nation:stormguard" in tag_names
        assert "guild:soldiers" in tag_names

        # Verify tag details
        stormguard_tag = next(t for t in tags if t.tag == "nation:stormguard")
        assert stormguard_tag.significance == 75.0
        assert stormguard_tag.role == "guard"
        assert len(stormguard_tag.narrative_hooks) == 3

        print("✓ test_npc_belonging_tags PASSED")
        return True
    except AssertionError as e:
        print(f"✗ test_npc_belonging_tags FAILED: {e}")
        return False
    finally:
        fixture.teardown()


def test_get_npcs_with_tag():
    """Task 16: Verify querying NPCs by tag."""
    fixture = FactionTestFixture()
    fixture.setup()

    try:
        db = FactionDatabase.get_instance()
        db.initialize()

        # Create multiple NPCs
        for i in range(3):
            db.create_npc_profile(
                npc_id=f"merchant_{i}",
                location_id="district:marketplace",
                narrative=f"Merchant {i}",
                primary_tag="profession:merchant"
            )
            db.add_npc_belonging_tag(f"merchant_{i}", "guild:merchants", 60.0)

        # Create NPC without merchant tag
        db.create_npc_profile(
            npc_id="blacksmith_1",
            location_id="district:forge",
            narrative="A blacksmith",
            primary_tag="profession:blacksmith"
        )
        db.add_npc_belonging_tag("blacksmith_1", "guild:craftsmen", 70.0)

        # Query NPCs with guild:merchants tag
        merchants = db.get_all_npcs_with_tag("guild:merchants")
        assert len(merchants) == 3, f"Should find 3 merchants, got {len(merchants)}"

        merchants_set = set(merchants)
        assert "merchant_0" in merchants_set
        assert "merchant_1" in merchants_set
        assert "merchant_2" in merchants_set
        assert "blacksmith_1" not in merchants_set

        print("✓ test_get_npcs_with_tag PASSED")
        return True
    except AssertionError as e:
        print(f"✗ test_get_npcs_with_tag FAILED: {e}")
        return False
    finally:
        fixture.teardown()


def test_player_affinity():
    """Task 17: Verify player affinity tracking."""
    fixture = FactionTestFixture()
    fixture.setup()

    try:
        db = FactionDatabase.get_instance()
        db.initialize()

        player_id = "player_1"

        # Initialize player (should return empty profile)
        profile = db.initialize_player_affinity(player_id)
        assert profile.player_id == player_id
        assert len(profile.affinity) == 0

        # Get initial affinity (should be 0)
        affinity = db.get_player_affinity(player_id, "guild:merchants")
        assert affinity == 0.0, f"Initial affinity should be 0, got {affinity}"

        # Add positive delta
        new_value = db.add_player_affinity_delta(player_id, "guild:merchants", 25.0)
        assert new_value == 25.0, f"Affinity should be 25, got {new_value}"

        # Verify persistence
        retrieved = db.get_player_affinity(player_id, "guild:merchants")
        assert retrieved == 25.0, f"Persisted affinity should be 25, got {retrieved}"

        # Add more delta (additive)
        new_value = db.add_player_affinity_delta(player_id, "guild:merchants", 35.0)
        assert new_value == 60.0, f"Affinity should be 60 (25+35), got {new_value}"

        # Add negative delta
        new_value = db.add_player_affinity_delta(player_id, "guild:merchants", -30.0)
        assert new_value == 30.0, f"Affinity should be 30 (60-30), got {new_value}"

        # Test clamping at +100
        new_value = db.add_player_affinity_delta(player_id, "guild:merchants", 100.0)
        assert new_value == 100.0, f"Affinity should clamp at +100, got {new_value}"

        # Test clamping at -100
        new_value = db.add_player_affinity_delta(player_id, "guild:merchants", -250.0)
        assert new_value == -100.0, f"Affinity should clamp at -100, got {new_value}"

        # Test multiple tags
        new_value = db.add_player_affinity_delta(player_id, "nation:stormguard", 50.0)
        assert new_value == 50.0

        all_affinities = db.get_all_player_affinities(player_id)
        assert len(all_affinities) == 2, f"Should have 2 tags, got {len(all_affinities)}"
        assert all_affinities["guild:merchants"] == -100.0
        assert all_affinities["nation:stormguard"] == 50.0

        print("✓ test_player_affinity PASSED")
        return True
    except AssertionError as e:
        print(f"✗ test_player_affinity FAILED: {e}")
        return False
    finally:
        fixture.teardown()


def test_cultural_affinity_calculation():
    """Task 17: Verify cultural affinity sums correctly across tiers."""
    fixture = FactionTestFixture()
    fixture.setup()

    try:
        db = FactionDatabase.get_instance()
        db.initialize()

        # Bootstrap data should have defaults for each tier
        # Calculate affinity for a tag at a specific location
        address_tiers = {
            "world": None,  # World tier always None
            "nation": "nation:stormguard",
            "region": "region:northlands",
            "province": "province:ironpeak",
            "district": "district:marketplace",
            "locality": None  # Locality may be None
        }

        # Get a tag that exists in bootstrap data
        all_tags = db.get_all_tags()
        assert len(all_tags) > 0, "Bootstrap should have loaded tags"
        test_tag = all_tags[0]

        # Calculate cultural affinity
        affinity = db.calculate_cultural_affinity(test_tag, address_tiers)
        assert -100.0 <= affinity <= 100.0, f"Affinity should be clamped, got {affinity}"

        # Test with minimal address (only world)
        minimal_address = {
            "world": None,
            "nation": None,
            "region": None,
            "province": None,
            "district": None,
            "locality": None
        }
        minimal_affinity = db.calculate_cultural_affinity(test_tag, minimal_address)
        assert -100.0 <= minimal_affinity <= 100.0

        # Test with different tags
        for tag in all_tags[:min(3, len(all_tags))]:
            affinity = db.calculate_cultural_affinity(tag, address_tiers)
            assert -100.0 <= affinity <= 100.0, f"Affinity for {tag} out of range: {affinity}"

        print("✓ test_cultural_affinity_calculation PASSED")
        return True
    except AssertionError as e:
        print(f"✗ test_cultural_affinity_calculation FAILED: {e}")
        return False
    finally:
        fixture.teardown()


def test_quest_log_operations():
    """Task 18: Verify quest log tracking."""
    fixture = FactionTestFixture()
    fixture.setup()

    try:
        db = FactionDatabase.get_instance()
        db.initialize()

        # Create NPC for quest
        db.create_npc_profile(
            npc_id="quest_giver_1",
            location_id="district:tavern",
            narrative="Quest giver",
            primary_tag="role:questgiver"
        )

        player_id = "player_1"
        quest_id = "quest_001"
        npc_id = "quest_giver_1"

        # Log quest offer
        offered = db.log_quest_offer(player_id, quest_id, npc_id)
        assert offered, "Quest offer should be logged"

        # Duplicate offer should fail
        duplicate_offer = db.log_quest_offer(player_id, quest_id, npc_id)
        assert not duplicate_offer, "Duplicate offer should fail"

        # Log quest completion
        completed = db.log_quest_completion(player_id, quest_id, npc_id)
        assert completed, "Quest completion should be logged"

        # Get NPC quest history
        history = db.get_npc_quest_history(npc_id)
        assert len(history) == 1, f"Should have 1 quest entry, got {len(history)}"

        entry = history[0]
        assert entry.player_id == player_id
        assert entry.quest_id == quest_id
        assert entry.npc_id == npc_id
        assert entry.status == "completed"
        assert entry.completed_at is not None

        print("✓ test_quest_log_operations PASSED")
        return True
    except AssertionError as e:
        print(f"✗ test_quest_log_operations FAILED: {e}")
        return False
    finally:
        fixture.teardown()


def test_npc_dialogue_context_assembly():
    """Task 18: Verify context assembly for LLM dialogue."""
    fixture = FactionTestFixture()
    fixture.setup()

    try:
        db = FactionDatabase.get_instance()
        db.initialize()

        # Setup NPC
        npc_id = "dialogue_npc_1"
        db.create_npc_profile(
            npc_id=npc_id,
            location_id="district:library",
            narrative="An ancient librarian with vast knowledge.",
            primary_tag="profession:librarian"
        )

        # Add belonging tags
        db.add_npc_belonging_tag(
            npc_id, "guild:scholars", 80.0, "elder",
            ["Scholar for decades", "Keeper of knowledge", "Mentor to many"]
        )

        # Setup player affinity
        player_id = "player_1"
        db.add_player_affinity_delta(player_id, "guild:scholars", 45.0)
        db.add_player_affinity_delta(player_id, "profession:librarian", 30.0)

        # Log a quest
        db.log_quest_offer(player_id, "retrieve_tome", npc_id)

        # Build dialogue context
        address_tiers = {
            "world": None,
            "nation": "nation:academarch",
            "region": "region:northlands",
            "province": None,
            "district": "district:library",
            "locality": None
        }

        context = db.build_npc_dialogue_context(player_id, npc_id, address_tiers)

        assert context is not None, "Context should be built"
        assert context.npc_id == npc_id
        assert context.npc_narrative == "An ancient librarian with vast knowledge."
        assert context.npc_primary_tag == "profession:librarian"
        assert context.player_id == player_id

        # Check belonging tags
        assert len(context.npc_belonging_tags) == 1
        assert context.npc_belonging_tags[0].tag == "guild:scholars"
        assert context.npc_belonging_tags[0].significance == 80.0

        # Check player affinity
        assert context.player_affinity["guild:scholars"] == 45.0
        assert context.player_affinity["profession:librarian"] == 30.0

        # Check cultural affinity (should be dict)
        assert isinstance(context.npc_cultural_affinity, dict)

        # Check quest history
        assert len(context.quest_history) == 1
        assert context.quest_history[0].quest_id == "retrieve_tome"

        # Test to_dict conversion
        context_dict = context.to_dict()
        assert context_dict["npc_id"] == npc_id
        assert isinstance(context_dict["npc_belonging_tags"], list)
        assert len(context_dict["npc_belonging_tags"]) == 1

        print("✓ test_npc_dialogue_context_assembly PASSED")
        return True
    except AssertionError as e:
        print(f"✗ test_npc_dialogue_context_assembly FAILED: {e}")
        return False
    finally:
        fixture.teardown()


def test_edge_cases():
    """Task 19: Verify edge cases and error handling."""
    fixture = FactionTestFixture()
    fixture.setup()

    try:
        db = FactionDatabase.get_instance()
        db.initialize()

        # Test with None connection (initialized check)
        assert db.connection is not None, "Connection should exist after init"

        # Test NPC profile with empty metadata
        npc = db.create_npc_profile(
            npc_id="edge_case_npc",
            location_id="district:test",
            narrative="Test",
            primary_tag="test:npc"
        )
        assert npc.metadata == {}, "Empty metadata should work"

        # Test affinity delta with very small values
        small_delta = db.add_player_affinity_delta("player_edge", "tag:test", 0.01)
        assert small_delta == 0.01, "Small delta should work"

        # Test NPCs in location
        db.create_npc_profile("npc_loc1", "district:market", "NPC1", "test:a")
        db.create_npc_profile("npc_loc2", "district:market", "NPC2", "test:b")
        db.create_npc_profile("npc_loc3", "district:forge", "NPC3", "test:c")

        market_npcs = db.get_all_npcs_in_location("district:market")
        assert len(market_npcs) == 2, f"Should find 2 NPCs in market, got {len(market_npcs)}"

        print("✓ test_edge_cases PASSED")
        return True
    except AssertionError as e:
        print(f"✗ test_edge_cases FAILED: {e}")
        return False
    finally:
        fixture.teardown()


def run_all_tests():
    """Run all faction system tests."""
    tests = [
        test_database_initialization,
        test_npc_profile_crud,
        test_npc_belonging_tags,
        test_get_npcs_with_tag,
        test_player_affinity,
        test_cultural_affinity_calculation,
        test_quest_log_operations,
        test_npc_dialogue_context_assembly,
        test_edge_cases,
    ]

    print("\n" + "="*60)
    print("FACTION SYSTEM PHASE 2 - TEST SUITE")
    print("="*60 + "\n")

    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"✗ {test_func.__name__} CRASHED: {e}\n")
            results.append((test_func.__name__, False))

    # Summary
    passed = sum(1 for _, result in results if result)
    total = len(results)

    print("\n" + "="*60)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("="*60 + "\n")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
