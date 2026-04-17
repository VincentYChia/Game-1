"""Affinity Defaults - hierarchical affinity values at different geographic scales.

Manages a hierarchy of affinity defaults: world → nation → region → province →
district → locality. When querying NPC affinity toward a tag, lookups check the
hierarchy and return the first non-None value found.

This allows efficient per-location affinity tuning without storing per-NPC values
for shared sentiment (e.g., "most NPCs in this nation distrust merchants").

Usage:
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
    result = affinity.lookup("guild:merchants", hierarchy)  # Returns -0.2
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, ClassVar, List, Tuple
import time


class AffinityDefaults:
    """Hierarchical affinity default values at geographic scales.

    Supports lazy initialization of hierarchy tiers and fallback lookup.
    Persists to disk as affinity-defaults.json.
    """

    _instance: ClassVar[Optional[AffinityDefaults]] = None

    # Hierarchy tiers (ordered from fine to coarse)
    TIERS = ["locality", "district", "province", "region", "nation", "world"]

    def __init__(self, config_path: str = "world_system/config/affinity-defaults.json"):
        self.config_path = Path(config_path)
        # Each tier maps location_id → {tag → affinity_value}
        self.defaults: Dict[str, Dict[str, Dict[str, float]]] = {
            "world": {},      # world → {tag → float}
            "nation": {},     # nation_id → {tag → float}
            "region": {},     # region_id → {tag → float}
            "province": {},   # province_id → {tag → float}
            "district": {},   # district_id → {tag → float}
            "locality": {}    # locality_id → {tag → float}
        }
        self._modified = False
        self._load()

    @classmethod
    def get_instance(cls) -> AffinityDefaults:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def _load(self) -> None:
        """Load affinity defaults from disk, or initialize empty."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self.defaults = data.get('affinity_defaults', self.defaults)
                print(f"✓ Loaded affinity defaults from {self.config_path.name}")
            except Exception as e:
                print(f"⚠ Error loading affinity defaults: {e}")
                self.defaults = {tier: {} for tier in self.TIERS}
        else:
            self.defaults = {tier: {} for tier in self.TIERS}
            self._modified = True

    def save(self) -> None:
        """Persist affinity defaults to disk."""
        if not self._modified and self.config_path.exists():
            return

        try:
            data = {
                "metadata": {
                    "version": 1,
                    "last_updated": time.time(),
                    "description": "Hierarchical affinity defaults: world → nation → region → province → district → locality"
                },
                "affinity_defaults": self.defaults
            }
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"✓ Saved affinity defaults to {self.config_path.name}")
            self._modified = False
        except Exception as e:
            print(f"✗ Error saving affinity defaults: {e}")

    def lookup(self, tag: str, location_hierarchy: Dict[str, Optional[str]]) -> float:
        """Lookup affinity for a tag in a location hierarchy.

        Checks hierarchy from fine to coarse: locality → district → province →
        region → nation → world. Returns the first non-None value found.

        Args:
            tag: Tag to look up (e.g., "guild:merchants")
            location_hierarchy: {
                "locality": "village_westhollow" or None,
                "district": "district_whispering_woods" or None,
                "province": "province_iron_hills" or None,
                "region": "region:northern_marches" or None,
                "nation": "nation:stormguard" or None,
                "world": None (always None; acts as fallback)
            }

        Returns:
            float affinity (0.0 if not found in hierarchy)
        """
        # Check tiers from fine to coarse
        for tier in self.TIERS:
            location_id = location_hierarchy.get(tier)
            if location_id is None:
                continue

            tier_data = self.defaults.get(tier, {})
            if location_id in tier_data:
                affinity = tier_data[location_id].get(tag)
                if affinity is not None:
                    return affinity

        # Fallback: check world-level defaults
        world_data = self.defaults.get("world", {})
        affinity = world_data.get(tag)
        return affinity if affinity is not None else 0.0

    def lookup_chain(self, tag: str, location_hierarchy: Dict[str, Optional[str]]) -> List[Tuple[str, float]]:
        """Lookup affinity for a tag and return the full resolution chain.

        Useful for debugging: shows which tier the affinity came from.

        Args:
            tag: Tag to look up
            location_hierarchy: Location hierarchy dict

        Returns:
            List of (tier_name, affinity_value) tuples showing resolution chain
        """
        chain = []
        for tier in self.TIERS:
            location_id = location_hierarchy.get(tier)
            if location_id is None:
                continue

            tier_data = self.defaults.get(tier, {})
            if location_id in tier_data:
                affinity = tier_data[location_id].get(tag)
                if affinity is not None:
                    chain.append((tier, affinity))
                    return chain

        # Add world fallback
        world_data = self.defaults.get("world", {})
        affinity = world_data.get(tag, 0.0)
        chain.append(("world", affinity))
        return chain

    # Setters for each tier

    def set_world_affinity(self, tag: str, value: float) -> None:
        """Set world-level affinity for a tag."""
        self.defaults["world"][tag] = value
        self._modified = True

    def set_nation_affinity(self, nation_id: str, tag: str, value: float) -> None:
        """Set nation-level affinity for a tag."""
        if nation_id not in self.defaults["nation"]:
            self.defaults["nation"][nation_id] = {}
        self.defaults["nation"][nation_id][tag] = value
        self._modified = True

    def set_region_affinity(self, region_id: str, tag: str, value: float) -> None:
        """Set region-level affinity for a tag."""
        if region_id not in self.defaults["region"]:
            self.defaults["region"][region_id] = {}
        self.defaults["region"][region_id][tag] = value
        self._modified = True

    def set_province_affinity(self, province_id: str, tag: str, value: float) -> None:
        """Set province-level affinity for a tag."""
        if province_id not in self.defaults["province"]:
            self.defaults["province"][province_id] = {}
        self.defaults["province"][province_id][tag] = value
        self._modified = True

    def set_district_affinity(self, district_id: str, tag: str, value: float) -> None:
        """Set district-level affinity for a tag."""
        if district_id not in self.defaults["district"]:
            self.defaults["district"][district_id] = {}
        self.defaults["district"][district_id][tag] = value
        self._modified = True

    def set_locality_affinity(self, locality_id: str, tag: str, value: float) -> None:
        """Set locality-level affinity for a tag."""
        if locality_id not in self.defaults["locality"]:
            self.defaults["locality"][locality_id] = {}
        self.defaults["locality"][locality_id][tag] = value
        self._modified = True

    # Getters

    def get_world_affinity(self, tag: str) -> Optional[float]:
        """Get world-level affinity for a tag."""
        return self.defaults["world"].get(tag)

    def get_nation_affinity(self, nation_id: str, tag: str) -> Optional[float]:
        """Get nation-level affinity for a tag."""
        return self.defaults["nation"].get(nation_id, {}).get(tag)

    def get_region_affinity(self, region_id: str, tag: str) -> Optional[float]:
        """Get region-level affinity for a tag."""
        return self.defaults["region"].get(region_id, {}).get(tag)

    def get_province_affinity(self, province_id: str, tag: str) -> Optional[float]:
        """Get province-level affinity for a tag."""
        return self.defaults["province"].get(province_id, {}).get(tag)

    def get_district_affinity(self, district_id: str, tag: str) -> Optional[float]:
        """Get district-level affinity for a tag."""
        return self.defaults["district"].get(district_id, {}).get(tag)

    def get_locality_affinity(self, locality_id: str, tag: str) -> Optional[float]:
        """Get locality-level affinity for a tag."""
        return self.defaults["locality"].get(locality_id, {}).get(tag)

    # Utility methods

    def clear_tier(self, tier: str) -> None:
        """Clear all affinities from a tier (for testing)."""
        if tier in self.defaults:
            self.defaults[tier] = {}
            self._modified = True

    def get_all_tags_in_tier(self, tier: str, location_id: Optional[str] = None) -> Dict[str, float]:
        """Get all tag affinities for a location in a specific tier.

        Args:
            tier: Tier name (e.g., "nation")
            location_id: If provided, get affinities for this location only.
                        If None, get all world-level (for world tier).

        Returns:
            Dictionary of {tag → affinity}
        """
        if tier == "world":
            return self.defaults.get("world", {}).copy()
        elif location_id:
            return self.defaults.get(tier, {}).get(location_id, {}).copy()
        else:
            # Merge all locations in tier
            merged = {}
            for location_affinities in self.defaults.get(tier, {}).values():
                merged.update(location_affinities)
            return merged

    def has_affinity(self, tag: str, location_hierarchy: Dict[str, Optional[str]]) -> bool:
        """Check if a tag has a non-zero affinity in the hierarchy."""
        return self.lookup(tag, location_hierarchy) != 0.0

    def remove_affinity(self, tier: str, location_id: Optional[str], tag: str) -> bool:
        """Remove a specific affinity value.

        Args:
            tier: Tier name
            location_id: Location within tier (None for world)
            tag: Tag to remove

        Returns:
            True if removed, False if didn't exist
        """
        if tier == "world":
            if tag in self.defaults["world"]:
                del self.defaults["world"][tag]
                self._modified = True
                return True
        elif location_id and tier in self.defaults:
            if location_id in self.defaults[tier]:
                if tag in self.defaults[tier][location_id]:
                    del self.defaults[tier][location_id][tag]
                    self._modified = True
                    return True
        return False
