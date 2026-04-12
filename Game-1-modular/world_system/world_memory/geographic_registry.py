"""Geographic Registry — named region hierarchy overlaid on the chunk grid.

Maps every position to a human-readable address:
  Realm > Nation > Province > District > Locality

Regions carry identity tags for interest-matching with entities and events.
Loaded from JSON configuration; supports runtime additions.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional, Tuple


class RegionLevel(Enum):
    LOCALITY = "locality"
    DISTRICT = "district"
    PROVINCE = "province"
    NATION = "nation"
    REALM = "realm"


@dataclass
class RegionState:
    """Mutable state of a region — updated by the aggregation pipeline."""
    active_conditions: List[str] = field(default_factory=list)
    recent_events: List[str] = field(default_factory=list)
    summary_text: str = ""
    last_updated: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_conditions": self.active_conditions,
            "recent_events": self.recent_events,
            "summary_text": self.summary_text,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RegionState:
        return cls(
            active_conditions=data.get("active_conditions", []),
            recent_events=data.get("recent_events", []),
            summary_text=data.get("summary_text", ""),
            last_updated=data.get("last_updated", 0.0),
        )


@dataclass
class Region:
    """A named geographic region at any level of the hierarchy."""
    region_id: str
    name: str
    level: RegionLevel

    # Spatial bounds (tile coordinates, axis-aligned rectangle)
    bounds_x1: int
    bounds_y1: int
    bounds_x2: int
    bounds_y2: int

    # Hierarchy
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)

    # Identity
    biome_primary: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)

    # Mutable state
    state: RegionState = field(default_factory=RegionState)

    @property
    def center(self) -> Tuple[float, float]:
        return (
            (self.bounds_x1 + self.bounds_x2) / 2.0,
            (self.bounds_y1 + self.bounds_y2) / 2.0,
        )

    @property
    def area(self) -> float:
        return (self.bounds_x2 - self.bounds_x1) * (self.bounds_y2 - self.bounds_y1)

    def contains(self, x: float, y: float) -> bool:
        return (self.bounds_x1 <= x <= self.bounds_x2 and
                self.bounds_y1 <= y <= self.bounds_y2)


class GeographicRegistry:
    """Maps positions to named regions. Singleton.

    Supports loading from a static JSON map, procedural generation from
    biome data, and runtime additions (discovered regions).
    """

    _instance: ClassVar[Optional[GeographicRegistry]] = None

    def __init__(self):
        self.regions: Dict[str, Region] = {}
        self.realm: Optional[Region] = None

        # Caches
        self._chunk_to_locality: Dict[Tuple[int, int], Optional[str]] = {}
        self._locality_chain: Dict[str, Dict[str, str]] = {}

    @classmethod
    def get_instance(cls) -> GeographicRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    # ── Loading ──────────────────────────────────────────────────────

    def load_base_map(self, filepath: str) -> None:
        """Load region definitions from a JSON map file."""
        if not os.path.exists(filepath):
            print(f"[GeoRegistry] Map file not found: {filepath} — starting empty")
            return

        with open(filepath, "r") as f:
            data = json.load(f)

        # Load realm
        if "realm" in data:
            r = data["realm"]
            realm = self._parse_region(r)
            self.regions[realm.region_id] = realm
            self.realm = realm

        # Load provinces, districts, localities
        for level_key in ("provinces", "districts", "localities"):
            for r in data.get(level_key, []):
                region = self._parse_region(r)
                self.regions[region.region_id] = region
                # Wire parent → child
                if region.parent_id and region.parent_id in self.regions:
                    parent = self.regions[region.parent_id]
                    if region.region_id not in parent.child_ids:
                        parent.child_ids.append(region.region_id)

        self._invalidate_cache()
        print(f"[GeoRegistry] Loaded {len(self.regions)} regions from {filepath}")

    def _parse_region(self, data: Dict[str, Any]) -> Region:
        bounds = data.get("bounds", [0, 0, 0, 0])
        return Region(
            region_id=data["region_id"],
            name=data["name"],
            level=RegionLevel(data["level"]),
            bounds_x1=bounds[0],
            bounds_y1=bounds[1],
            bounds_x2=bounds[2],
            bounds_y2=bounds[3],
            parent_id=data.get("parent_id"),
            child_ids=data.get("child_ids", []),
            biome_primary=data.get("biome_primary", ""),
            description=data.get("description", ""),
            tags=data.get("tags", []),
        )

    def load_from_world_map(self, world_map) -> None:
        """Load region hierarchy from the geographic system's WorldMap.

        Maps the game's 5-tier hierarchy 1:1 to WMS levels:
            Game Nation   → WMS NATION
            Game Region   → WMS PROVINCE  (Layer 4 scope)
            Game Province → WMS DISTRICT  (Layer 3 scope)
            Game District → WMS LOCALITY  (Layer 2 scope / position lookup)

        Args:
            world_map: WorldMap from systems.geography.models
        """
        self.regions.clear()
        self._invalidate_cache()
        chunk_size = 16

        # Create realm
        half = world_map.world_size // 2
        realm_bounds = [-half * chunk_size, -half * chunk_size,
                        half * chunk_size, half * chunk_size]
        realm = Region(
            region_id="realm_0",
            name="The Known Lands",
            level=RegionLevel.REALM,
            bounds_x1=realm_bounds[0], bounds_y1=realm_bounds[1],
            bounds_x2=realm_bounds[2], bounds_y2=realm_bounds[3],
        )
        self.regions["realm_0"] = realm
        self.realm = realm

        # Register nations as NATION (highest named division)
        for nid, nation in world_map.nations.items():
            nation_id = f"nation_{nid}"
            child_ids = []
            min_x, min_y = float('inf'), float('inf')
            max_x, max_y = float('-inf'), float('-inf')
            for rid in nation.region_ids:
                region = world_map.regions.get(rid)
                if region:
                    bx1, by1, bx2, by2 = region.bounds
                    min_x = min(min_x, bx1 * chunk_size)
                    min_y = min(min_y, by1 * chunk_size)
                    max_x = max(max_x, bx2 * chunk_size)
                    max_y = max(max_y, by2 * chunk_size)
                    child_ids.append(f"region_{rid}")

            self.regions[nation_id] = Region(
                region_id=nation_id,
                name=nation.name,
                level=RegionLevel.NATION,
                bounds_x1=int(min_x) if min_x != float('inf') else 0,
                bounds_y1=int(min_y) if min_y != float('inf') else 0,
                bounds_x2=int(max_x) if max_x != float('-inf') else 0,
                bounds_y2=int(max_y) if max_y != float('-inf') else 0,
                parent_id="realm_0",
                child_ids=child_ids,
                tags=[f"nation:{nation.name.lower()}", f"flavor:{nation.naming_flavor.value}"],
            )
            realm.child_ids.append(nation_id)

        # Register game regions as PROVINCE (Layer 4 scope)
        for rid, region in world_map.regions.items():
            region_id = f"region_{rid}"
            bx1, by1, bx2, by2 = region.bounds
            nation = world_map.nations.get(region.nation_id)
            parent_id = f"nation_{region.nation_id}"

            # Children are game provinces (WMS districts)
            child_ids = [f"province_{pid}" for pid in region.province_ids]

            self.regions[region_id] = Region(
                region_id=region_id,
                name=region.name,
                level=RegionLevel.PROVINCE,
                bounds_x1=bx1 * chunk_size, bounds_y1=by1 * chunk_size,
                bounds_x2=bx2 * chunk_size, bounds_y2=by2 * chunk_size,
                parent_id=parent_id,
                child_ids=child_ids,
                biome_primary=region.identity.value,
                tags=[f"identity:{region.identity.value}",
                      f"nation:{nation.name.lower()}" if nation else ""],
            )

        # Register game provinces as DISTRICT (Layer 3 scope)
        for pid, province in world_map.provinces.items():
            province_id = f"province_{pid}"
            bx1, by1, bx2, by2 = province.bounds
            parent_id = f"region_{province.region_id}"

            # Children are game districts (WMS localities)
            child_ids = []
            if hasattr(province, 'district_ids'):
                child_ids = [f"district_{did}" for did in province.district_ids]

            self.regions[province_id] = Region(
                region_id=province_id,
                name=province.name,
                level=RegionLevel.DISTRICT,
                bounds_x1=bx1 * chunk_size, bounds_y1=by1 * chunk_size,
                bounds_x2=bx2 * chunk_size, bounds_y2=by2 * chunk_size,
                parent_id=parent_id,
                child_ids=child_ids,
            )

        # Register game districts as LOCALITY (position lookup)
        if hasattr(world_map, 'districts') and world_map.districts:
            for did, district in world_map.districts.items():
                district_id = f"district_{did}"
                bx1, by1, bx2, by2 = district.bounds
                parent_id = f"province_{district.province_id}"

                self.regions[district_id] = Region(
                    region_id=district_id,
                    name=district.name,
                    level=RegionLevel.LOCALITY,
                    bounds_x1=bx1 * chunk_size, bounds_y1=by1 * chunk_size,
                    bounds_x2=bx2 * chunk_size, bounds_y2=by2 * chunk_size,
                    parent_id=parent_id,
                )

        self._invalidate_cache()
        nn = len(world_map.nations)
        nr = len(world_map.regions)
        np_ = len(world_map.provinces)
        nd = len(world_map.districts) if hasattr(world_map, 'districts') else 0
        print(f"[GeoRegistry] Loaded from WorldMap: "
              f"{nn} nations, {nr} regions/provinces, "
              f"{np_} provinces/districts, {nd} districts/localities")

    def generate_from_biomes(self, chunk_biomes: Dict[Tuple[int, int], str],
                             chunk_size: int = 16) -> None:
        """Generate a basic region hierarchy from chunk biome data.

        Groups chunks by biome type into localities, then clusters
        localities into districts and provinces.
        """
        if not chunk_biomes:
            return

        # Find world bounds from chunk coordinates
        all_cx = [c[0] for c in chunk_biomes]
        all_cy = [c[1] for c in chunk_biomes]
        min_cx, max_cx = min(all_cx), max(all_cx)
        min_cy, max_cy = min(all_cy), max(all_cy)

        # Create realm covering entire known world
        realm = Region(
            region_id="known_lands",
            name="The Known Lands",
            level=RegionLevel.REALM,
            bounds_x1=min_cx * chunk_size,
            bounds_y1=min_cy * chunk_size,
            bounds_x2=(max_cx + 1) * chunk_size - 1,
            bounds_y2=(max_cy + 1) * chunk_size - 1,
            description="The explored world.",
        )
        self.regions[realm.region_id] = realm
        self.realm = realm

        # Group chunks into quadrant-based provinces
        mid_x = (min_cx + max_cx) // 2
        mid_y = (min_cy + max_cy) // 2
        quadrants = {
            "nw": (min_cx, min_cy, mid_x, mid_y, "Northwestern Reaches"),
            "ne": (mid_x + 1, min_cy, max_cx, mid_y, "Northeastern Highlands"),
            "sw": (min_cx, mid_y + 1, mid_x, max_cy, "Southwestern Lowlands"),
            "se": (mid_x + 1, mid_y + 1, max_cx, max_cy, "Southeastern Frontier"),
        }

        for qid, (cx1, cy1, cx2, cy2, name) in quadrants.items():
            prov_id = f"province_{qid}"
            province = Region(
                region_id=prov_id,
                name=name,
                level=RegionLevel.PROVINCE,
                bounds_x1=cx1 * chunk_size,
                bounds_y1=cy1 * chunk_size,
                bounds_x2=(cx2 + 1) * chunk_size - 1,
                bounds_y2=(cy2 + 1) * chunk_size - 1,
                parent_id=realm.region_id,
            )
            self.regions[prov_id] = province
            realm.child_ids.append(prov_id)

            # Create localities from individual chunks in this quadrant
            for (cx, cy), biome in chunk_biomes.items():
                if cx1 <= cx <= cx2 and cy1 <= cy <= cy2:
                    loc_id = f"loc_{cx}_{cy}"
                    biome_base = biome.replace("peaceful_", "").replace("dangerous_", "").replace("rare_", "").replace("hidden_", "").replace("ancient_", "").replace("deep_", "")
                    loc = Region(
                        region_id=loc_id,
                        name=f"{biome_base.replace('_', ' ').title()} ({cx},{cy})",
                        level=RegionLevel.LOCALITY,
                        bounds_x1=cx * chunk_size,
                        bounds_y1=cy * chunk_size,
                        bounds_x2=(cx + 1) * chunk_size - 1,
                        bounds_y2=(cy + 1) * chunk_size - 1,
                        parent_id=prov_id,
                        biome_primary=biome,
                        tags=[f"biome:{biome_base}", f"terrain:{biome_base}"],
                    )
                    self.regions[loc_id] = loc
                    province.child_ids.append(loc_id)

        self._invalidate_cache()
        print(f"[GeoRegistry] Generated {len(self.regions)} regions from biome data")

    # ── Lookup ───────────────────────────────────────────────────────

    def get_region_at(self, x: float, y: float) -> Optional[Region]:
        """Get the most specific (locality-level) region for a position."""
        chunk_x = int(x) // 16
        chunk_y = int(y) // 16
        cache_key = (chunk_x, chunk_y)

        if cache_key in self._chunk_to_locality:
            loc_id = self._chunk_to_locality[cache_key]
            return self.regions.get(loc_id) if loc_id else None

        # Scan localities
        for region in self.regions.values():
            if region.level == RegionLevel.LOCALITY and region.contains(x, y):
                self._chunk_to_locality[cache_key] = region.region_id
                return region

        self._chunk_to_locality[cache_key] = None
        return None

    def get_full_address(self, x: float, y: float) -> Dict[str, str]:
        """Get full address hierarchy: {locality, district, province, realm}."""
        locality = self.get_region_at(x, y)
        if not locality:
            return {}

        # Check chain cache
        if locality.region_id in self._locality_chain:
            return dict(self._locality_chain[locality.region_id])

        result: Dict[str, str] = {"locality": locality.region_id}
        current = locality
        while current.parent_id:
            parent = self.regions.get(current.parent_id)
            if not parent:
                break
            result[parent.level.value] = parent.region_id
            current = parent

        self._locality_chain[locality.region_id] = result
        return dict(result)

    def get_regions_by_level(self, level: RegionLevel) -> List[Region]:
        return [r for r in self.regions.values() if r.level == level]

    def get_regions_by_tag(self, tag: str) -> List[Region]:
        return [r for r in self.regions.values() if tag in r.tags]

    def get_nearby_regions(self, x: float, y: float, radius: float,
                           level: RegionLevel = RegionLevel.LOCALITY) -> List[Region]:
        results = []
        for region in self.regions.values():
            if region.level != level:
                continue
            cx, cy = region.center
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            if dist <= radius:
                results.append(region)
        return results

    def get_children(self, region_id: str) -> List[Region]:
        region = self.regions.get(region_id)
        if not region:
            return []
        return [self.regions[cid] for cid in region.child_ids
                if cid in self.regions]

    # ── Mutation ─────────────────────────────────────────────────────

    def register_region(self, region: Region) -> None:
        """Add a new region at runtime."""
        self.regions[region.region_id] = region
        if region.parent_id and region.parent_id in self.regions:
            parent = self.regions[region.parent_id]
            if region.region_id not in parent.child_ids:
                parent.child_ids.append(region.region_id)
        self._invalidate_cache()

    def _invalidate_cache(self) -> None:
        self._chunk_to_locality.clear()
        self._locality_chain.clear()

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize all region states (not definitions — those come from JSON)."""
        return {
            region_id: region.state.to_dict()
            for region_id, region in self.regions.items()
        }

    def restore_states(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Restore region states from save data."""
        for region_id, state_data in data.items():
            if region_id in self.regions:
                self.regions[region_id].state = RegionState.from_dict(state_data)
