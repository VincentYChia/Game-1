"""Test suite for Faction System Phase 1: TagRegistry and AffinityDefaults."""

import pytest
import json
import tempfile
from pathlib import Path
from world_system.faction.tag_registry import TagRegistry, TagEntry
from world_system.faction.affinity_defaults import AffinityDefaults


class TestTagRegistry:
    """Tests for TagRegistry singleton."""

    def setup_method(self):
        """Reset singleton before each test."""
        TagRegistry.reset()

    def teardown_method(self):
        """Clean up after each test."""
        TagRegistry.reset()

    def test_singleton_pattern(self):
        """Verify TagRegistry is a singleton."""
        reg1 = TagRegistry.get_instance()
        reg2 = TagRegistry.get_instance()
        assert reg1 is reg2

    def test_register_new_tag(self):
        """Register a new tag and verify it's stored."""
        registry = TagRegistry.get_instance()
        registry.register("nation:test", "nation", "A test nation")
        assert registry.validate_tag("nation:test")
        entry = registry.get("nation:test")
        assert entry.namespace == "nation"
        assert entry.human_gloss == "A test nation"

    def test_appearance_count_increment(self):
        """Verify appearance count increments on repeated registration."""
        registry = TagRegistry.get_instance()
        registry.register("guild:test", "guild", "A test guild")
        assert registry.appearance_count("guild:test") == 1
        registry.register("guild:test", "guild", "A test guild")
        assert registry.appearance_count("guild:test") == 2
        registry.register("guild:test", "guild", "A test guild")
        assert registry.appearance_count("guild:test") == 3

    def test_namespace_validation(self):
        """Test namespace validation."""
        registry = TagRegistry.get_instance()
        registry.register("nation:test", "nation", "Test")
        assert registry.validate_namespace("nation:test", "nation")
        assert not registry.validate_namespace("nation:test", "guild")

    def test_get_nonexistent_tag(self):
        """Getting a nonexistent tag returns None."""
        registry = TagRegistry.get_instance()
        assert registry.get("nonexistent:tag") is None

    def test_all_tags_unfiltered(self):
        """Get all tags without filtering."""
        registry = TagRegistry.get_instance()
        registry.register("nation:a", "nation", "Nation A")
        registry.register("guild:b", "guild", "Guild B")
        registry.register("nation:c", "nation", "Nation C")

        all_tags = registry.all_tags()
        assert len(all_tags) == 3

    def test_all_tags_filtered_by_namespace(self):
        """Get tags filtered by namespace."""
        registry = TagRegistry.get_instance()
        registry.register("nation:a", "nation", "Nation A")
        registry.register("guild:b", "guild", "Guild B")
        registry.register("nation:c", "nation", "Nation C")

        nation_tags = registry.all_tags(namespace="nation")
        assert len(nation_tags) == 2
        assert all(t.namespace == "nation" for t in nation_tags)

    def test_is_generated_flag(self):
        """Test tracking of LLM-generated tags."""
        registry = TagRegistry.get_instance()
        registry.register("cult:authored", "cult", "Hand-authored", is_generated=False)
        registry.register("cult:llm", "cult", "LLM-generated", is_generated=True)

        assert not registry.get("cult:authored").is_generated
        assert registry.get("cult:llm").is_generated

    def test_mark_generated(self):
        """Mark an existing tag as generated."""
        registry = TagRegistry.get_instance()
        registry.register("cult:test", "cult", "Test cult", is_generated=False)
        assert not registry.get("cult:test").is_generated

        registry.mark_generated("cult:test")
        assert registry.get("cult:test").is_generated

    def test_add_alias(self):
        """Add alias to a tag."""
        registry = TagRegistry.get_instance()
        registry.register("guild:merchants", "guild", "Merchant guild")

        success = registry.add_alias("guild:merchants", "guild:merchant_union")
        assert success
        assert "guild:merchant_union" in registry.get("guild:merchants").aliases

    def test_get_by_alias(self):
        """Look up tag by alias."""
        registry = TagRegistry.get_instance()
        registry.register("nation:test", "nation", "Test nation")
        registry.add_alias("nation:test", "nation:testland")

        entry = registry.get_by_alias("nation:testland")
        assert entry is not None
        assert entry.tag == "nation:test"

    def test_namespaces_list(self):
        """Get list of all unique namespaces."""
        registry = TagRegistry.get_instance()
        registry.register("nation:a", "nation", "N")
        registry.register("guild:b", "guild", "G")
        registry.register("profession:c", "profession", "P")
        registry.register("nation:d", "nation", "N")

        namespaces = registry.namespaces()
        assert set(namespaces) == {"nation", "guild", "profession"}

    def test_count_by_namespace(self):
        """Count tags in a namespace."""
        registry = TagRegistry.get_instance()
        registry.register("nation:a", "nation", "N")
        registry.register("nation:b", "nation", "N")
        registry.register("guild:c", "guild", "G")

        assert registry.count_by_namespace("nation") == 2
        assert registry.count_by_namespace("guild") == 1

    def test_persistence_save_load(self):
        """Test saving and loading from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test-registry.json")

            # Create registry with data
            TagRegistry.reset()
            reg1 = TagRegistry(config_path=config_path)
            reg1.register("nation:test", "nation", "Test nation")
            reg1.save()

            # Load in new instance
            TagRegistry.reset()
            reg2 = TagRegistry(config_path=config_path)
            assert reg2.validate_tag("nation:test")
            assert reg2.get("nation:test").human_gloss == "Test nation"

    def test_persistence_increment_count(self):
        """Test that appearance count persists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test-registry.json")

            # Create and save
            TagRegistry.reset()
            reg1 = TagRegistry(config_path=config_path)
            reg1.register("guild:test", "guild", "Test guild")
            reg1.register("guild:test", "guild", "Test guild")  # Increment
            reg1.save()

            # Load and verify count
            TagRegistry.reset()
            reg2 = TagRegistry(config_path=config_path)
            assert reg2.appearance_count("guild:test") == 2


class TestAffinityDefaults:
    """Tests for AffinityDefaults singleton."""

    def setup_method(self):
        """Reset singleton before each test."""
        AffinityDefaults.reset()

    def teardown_method(self):
        """Clean up after each test."""
        AffinityDefaults.reset()

    def test_singleton_pattern(self):
        """Verify AffinityDefaults is a singleton."""
        aff1 = AffinityDefaults.get_instance()
        aff2 = AffinityDefaults.get_instance()
        assert aff1 is aff2

    def test_set_world_affinity(self):
        """Set and retrieve world-level affinity."""
        affinity = AffinityDefaults.get_instance()
        affinity.set_world_affinity("guild:merchants", -0.1)
        assert affinity.get_world_affinity("guild:merchants") == -0.1

    def test_set_nation_affinity(self):
        """Set and retrieve nation-level affinity."""
        affinity = AffinityDefaults.get_instance()
        affinity.set_nation_affinity("nation:stormguard", "guild:merchants", -0.2)
        assert affinity.get_nation_affinity("nation:stormguard", "guild:merchants") == -0.2

    def test_set_locality_affinity(self):
        """Set and retrieve locality-level affinity."""
        affinity = AffinityDefaults.get_instance()
        affinity.set_locality_affinity("village_west", "guild:merchants", -0.3)
        assert affinity.get_locality_affinity("village_west", "guild:merchants") == -0.3

    def test_lookup_world_fallback(self):
        """Lookup with no specific location returns world value."""
        affinity = AffinityDefaults.get_instance()
        affinity.set_world_affinity("guild:merchants", -0.1)

        hierarchy = {
            "world": None,
            "nation": None,
            "region": None,
            "province": None,
            "district": None,
            "locality": None
        }
        assert affinity.lookup("guild:merchants", hierarchy) == -0.1

    def test_lookup_hierarchy_nation_overrides_world(self):
        """Nation-level affinity overrides world-level."""
        affinity = AffinityDefaults.get_instance()
        affinity.set_world_affinity("guild:merchants", -0.1)
        affinity.set_nation_affinity("nation:stormguard", "guild:merchants", -0.2)

        hierarchy = {
            "world": None,
            "nation": "nation:stormguard",
            "region": None,
            "province": None,
            "district": None,
            "locality": None
        }
        assert affinity.lookup("guild:merchants", hierarchy) == -0.2

    def test_lookup_hierarchy_locality_overrides_nation(self):
        """Locality-level affinity overrides nation-level."""
        affinity = AffinityDefaults.get_instance()
        affinity.set_world_affinity("guild:merchants", -0.1)
        affinity.set_nation_affinity("nation:stormguard", "guild:merchants", -0.2)
        affinity.set_locality_affinity("village_west", "guild:merchants", -0.3)

        hierarchy = {
            "world": None,
            "nation": "nation:stormguard",
            "region": None,
            "province": None,
            "district": None,
            "locality": "village_west"
        }
        assert affinity.lookup("guild:merchants", hierarchy) == -0.3

    def test_lookup_nonexistent_returns_zero(self):
        """Lookup of nonexistent tag returns 0.0."""
        affinity = AffinityDefaults.get_instance()
        hierarchy = {
            "world": None,
            "nation": None,
            "region": None,
            "province": None,
            "district": None,
            "locality": None
        }
        assert affinity.lookup("nonexistent:tag", hierarchy) == 0.0

    def test_lookup_chain(self):
        """lookup_chain returns resolution path."""
        affinity = AffinityDefaults.get_instance()
        affinity.set_world_affinity("guild:merchants", -0.1)
        affinity.set_nation_affinity("nation:stormguard", "guild:merchants", -0.2)

        hierarchy = {
            "world": None,
            "nation": "nation:stormguard",
            "region": None,
            "province": None,
            "district": None,
            "locality": None
        }
        chain = affinity.lookup_chain("guild:merchants", hierarchy)
        assert len(chain) == 1
        assert chain[0] == ("nation", -0.2)

    def test_clear_tier(self):
        """Clearing a tier removes all affinities in it."""
        affinity = AffinityDefaults.get_instance()
        affinity.set_nation_affinity("nation:a", "tag:x", 0.5)
        affinity.set_nation_affinity("nation:a", "tag:y", 0.3)
        affinity.set_nation_affinity("nation:b", "tag:x", 0.1)

        affinity.clear_tier("nation")
        assert affinity.get_nation_affinity("nation:a", "tag:x") is None
        assert affinity.get_nation_affinity("nation:b", "tag:x") is None

    def test_get_all_tags_in_tier_world(self):
        """Get all world-level affinities."""
        affinity = AffinityDefaults.get_instance()
        affinity.set_world_affinity("guild:a", 0.1)
        affinity.set_world_affinity("guild:b", -0.2)

        tags = affinity.get_all_tags_in_tier("world")
        assert tags["guild:a"] == 0.1
        assert tags["guild:b"] == -0.2

    def test_get_all_tags_in_tier_location(self):
        """Get all affinities for a specific location."""
        affinity = AffinityDefaults.get_instance()
        affinity.set_nation_affinity("nation:a", "tag:x", 0.5)
        affinity.set_nation_affinity("nation:a", "tag:y", 0.3)
        affinity.set_nation_affinity("nation:b", "tag:x", 0.1)

        tags = affinity.get_all_tags_in_tier("nation", "nation:a")
        assert len(tags) == 2
        assert tags["tag:x"] == 0.5
        assert tags["tag:y"] == 0.3

    def test_has_affinity(self):
        """Check if affinity exists in hierarchy."""
        affinity = AffinityDefaults.get_instance()
        affinity.set_world_affinity("guild:test", 0.0)  # Zero is "no affinity"
        affinity.set_world_affinity("guild:other", 0.5)

        hierarchy = {"world": None, "nation": None, "region": None,
                     "province": None, "district": None, "locality": None}

        assert not affinity.has_affinity("guild:test", hierarchy)  # Zero = no
        assert affinity.has_affinity("guild:other", hierarchy)

    def test_remove_affinity_world(self):
        """Remove world-level affinity."""
        affinity = AffinityDefaults.get_instance()
        affinity.set_world_affinity("guild:test", 0.5)
        assert affinity.get_world_affinity("guild:test") == 0.5

        success = affinity.remove_affinity("world", None, "guild:test")
        assert success
        assert affinity.get_world_affinity("guild:test") is None

    def test_remove_affinity_location(self):
        """Remove location-specific affinity."""
        affinity = AffinityDefaults.get_instance()
        affinity.set_nation_affinity("nation:a", "guild:test", 0.5)

        success = affinity.remove_affinity("nation", "nation:a", "guild:test")
        assert success
        assert affinity.get_nation_affinity("nation:a", "guild:test") is None

    def test_persistence_save_load(self):
        """Test saving and loading from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = str(Path(tmpdir) / "test-affinity.json")

            # Create and save
            AffinityDefaults.reset()
            aff1 = AffinityDefaults(config_path=config_path)
            aff1.set_world_affinity("guild:merchants", -0.1)
            aff1.set_nation_affinity("nation:stormguard", "guild:merchants", -0.2)
            aff1.save()

            # Load in new instance
            AffinityDefaults.reset()
            aff2 = AffinityDefaults(config_path=config_path)
            assert aff2.get_world_affinity("guild:merchants") == -0.1
            assert aff2.get_nation_affinity("nation:stormguard", "guild:merchants") == -0.2


class TestIntegration:
    """Integration tests between TagRegistry and AffinityDefaults."""

    def setup_method(self):
        """Reset singletons before each test."""
        TagRegistry.reset()
        AffinityDefaults.reset()

    def teardown_method(self):
        """Clean up after each test."""
        TagRegistry.reset()
        AffinityDefaults.reset()

    def test_register_tags_used_in_affinity(self):
        """Tags used in affinity should be registered."""
        registry = TagRegistry.get_instance()
        affinity = AffinityDefaults.get_instance()

        registry.register("guild:merchants", "guild", "Merchant guild")
        affinity.set_world_affinity("guild:merchants", -0.1)

        assert registry.validate_tag("guild:merchants")
        assert affinity.get_world_affinity("guild:merchants") == -0.1

    def test_location_hierarchy_with_multiple_affinities(self):
        """Complex hierarchy with multiple tags."""
        affinity = AffinityDefaults.get_instance()
        registry = TagRegistry.get_instance()

        # Register tags
        for tag in ["guild:merchants", "profession:guard", "ideology:separatist"]:
            parts = tag.split(":")
            registry.register(tag, parts[0], f"Test {tag}")

        # Set defaults
        affinity.set_world_affinity("guild:merchants", -0.1)
        affinity.set_nation_affinity("nation:stormguard", "guild:merchants", -0.2)
        affinity.set_nation_affinity("nation:stormguard", "profession:guard", 0.2)

        # Lookup
        hierarchy = {
            "world": None,
            "nation": "nation:stormguard",
            "region": None,
            "province": None,
            "district": None,
            "locality": None
        }

        assert affinity.lookup("guild:merchants", hierarchy) == -0.2
        assert affinity.lookup("profession:guard", hierarchy) == 0.2
        assert affinity.lookup("ideology:separatist", hierarchy) == -0.1  # Fallback to world


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
